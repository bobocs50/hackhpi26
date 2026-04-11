import logging
import os
import sys

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_BACKEND_ROOT = Path(__file__).resolve().parent
_BACKEND_SRC = _BACKEND_ROOT / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from reporting import build_report_response, load_default_run

import numpy as np
from agri_nav.dto.perception import CropOccupancyGrid
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.mapper.tracker_csv import DEFAULT_FPS, parse_tracker_csv
from agri_nav.service.apf_service import APFService, VehicleState
from agri_nav.service.sgg_service import SGGService

logger = logging.getLogger(__name__)

app = FastAPI(title="HackHPI Backend", version="0.1.0")
DATA_DIR = Path(__file__).resolve().parent / "data"
VISUAL_DATA_FIXTURE = DATA_DIR / "visual_data_fixture.json"
UPLOADS_DIR = DATA_DIR / "uploads"
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_RUN = load_default_run()

# -- agri-nav pipeline singletons --
_sgg_service = SGGService()
_apf_service = APFService()
_sgg_inference_cfg = SGGInferenceConfig(ego_vy=3.0)


class RunUploadResponse(BaseModel):
    run_id: str
    folder_name: str | None
    file_count: int
    status: Literal["processing"]


class RunFramesResponse(BaseModel):
    run_id: str
    folder_name: str | None
    file_count: int
    status: Literal["processing", "completed", "failed"]
    pipeline_stage: str | None = None
    final_output_ready: bool = False
    final_output_generated_at: str | None = None
    created_at: str
    updated_at: str
    tracker_status: Literal["processing", "completed", "failed"]
    tracker_started_at: str | None
    tracker_finished_at: str | None
    tracker_error: str | None
    frames: list[str]


_allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/mock-visual-data")
def get_mock_visual_data() -> dict:
    """Return live demo-scene visual data from the agri-nav pipeline.

    Falls back to the static fixture file if the pipeline fails.
    """
    try:
        return _run_demo_pipeline()
    except Exception:
        logger.exception("Demo pipeline failed — falling back to fixture")
        with VISUAL_DATA_FIXTURE.open("r", encoding="utf-8") as fixture_file:
            return json.load(fixture_file)


@app.get("/report")
def get_run_report() -> dict:
    return build_report_response(DEFAULT_RUN)


@app.post("/runs/upload-frames")
async def upload_run_frames(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    folder_name: str | None = Form(default=None),
) -> RunUploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    run_id = uuid4().hex
    run_dir = UPLOADS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    saved_files = 0
    saved_names: list[str] = []

    for file in files:
        filename = Path(file.filename or "").name
        suffix = Path(filename).suffix.lower()

        if not filename or suffix not in ALLOWED_IMAGE_SUFFIXES:
            await file.close()
            continue

        destination = run_dir / filename
        destination.write_bytes(await file.read())
        saved_files += 1
        saved_names.append(filename)
        await file.close()

    if saved_files == 0:
        raise HTTPException(status_code=400, detail="No supported image files were uploaded.")

    created_at = utc_now_iso()
    metadata = {
        "run_id": run_id,
        "folder_name": folder_name,
        "file_count": saved_files,
        "file_names": sorted(saved_names, key=sort_frame_names),
        "status": "processing",
        "pipeline_stage": "tracking",
        "final_output_ready": False,
        "final_output_generated_at": None,
        "final_output_path": None,
        "created_at": created_at,
        "updated_at": created_at,
        "tracker_status": "processing",
        "tracker_started_at": created_at,
        "tracker_finished_at": None,
        "tracker_error": None,
    }
    write_json(run_dir / "metadata.json", metadata)
    background_tasks.add_task(run_tracker_for_run, run_id)

    return RunUploadResponse(
        run_id=run_id,
        folder_name=folder_name,
        file_count=saved_files,
        status="processing",
    )


@app.get("/runs/{run_id}/frames")
def get_run_frames(run_id: str) -> RunFramesResponse:
    metadata = load_run_metadata_or_404(run_id)
    return RunFramesResponse(
        run_id=metadata["run_id"],
        folder_name=metadata.get("folder_name"),
        file_count=metadata["file_count"],
        status=metadata["status"],
        pipeline_stage=metadata.get("pipeline_stage"),
        final_output_ready=metadata.get("final_output_ready", False),
        final_output_generated_at=metadata.get("final_output_generated_at"),
        created_at=metadata["created_at"],
        updated_at=metadata["updated_at"],
        tracker_status=metadata.get("tracker_status", metadata["status"]),
        tracker_started_at=metadata.get("tracker_started_at"),
        tracker_finished_at=metadata.get("tracker_finished_at"),
        tracker_error=metadata.get("tracker_error"),
        frames=metadata.get("file_names", []),
    )


@app.get("/runs/{run_id}/visual-data")
def get_run_visual_data(run_id: str) -> dict:
    metadata = load_run_metadata_or_404(run_id)

    if not metadata.get("final_output_ready"):
        raise HTTPException(
            status_code=409,
            detail=f"Final output is not ready. Status: {metadata.get('status')}",
        )

    final_output_path = metadata.get("final_output_path")
    if not final_output_path:
        raise HTTPException(status_code=404, detail="Final output path is missing.")

    return read_json(Path(final_output_path))


def get_run_dir(run_id: str) -> Path:
    return UPLOADS_DIR / run_id


def load_run_metadata_or_404(run_id: str) -> dict[str, Any]:
    metadata_path = get_run_dir(run_id) / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Run not found.")

    return read_json(metadata_path)


def run_tracker_for_run(run_id: str) -> None:
    from yolo_tracker import run_yolo_tracker

    run_dir = get_run_dir(run_id)
    metadata = load_run_metadata_or_404(run_id)

    try:
        metadata["pipeline_stage"] = "tracking"
        write_json(run_dir / "metadata.json", metadata)

        tracker_output = run_yolo_tracker(run_dir, run_dir / "tracker")
        metadata["tracker_status"] = "completed"
        metadata["tracker_finished_at"] = utc_now_iso()
        metadata["tracker_error"] = None
        metadata["tracker_output"] = tracker_output
        metadata["updated_at"] = metadata["tracker_finished_at"]
        metadata["pipeline_stage"] = "assembling_final_output"
        write_json(run_dir / "metadata.json", metadata)

        final_output = build_run_final_output(run_id, metadata)
        final_output_path = run_dir / "final_output.json"
        write_json(final_output_path, final_output)
        print("Final uploaded-run output JSON:")
        print(json.dumps(final_output, indent=2))

        finished_at = utc_now_iso()
        metadata["status"] = "completed"
        metadata["updated_at"] = finished_at
        metadata["pipeline_stage"] = "completed"
        metadata["final_output_ready"] = True
        metadata["final_output_generated_at"] = finished_at
        metadata["final_output_path"] = str(final_output_path)
    except Exception as exc:
        finished_at = utc_now_iso()
        metadata["status"] = "failed"
        metadata["updated_at"] = finished_at
        metadata["pipeline_stage"] = "failed"
        if metadata.get("tracker_status") != "completed":
            metadata["tracker_status"] = "failed"
            metadata["tracker_finished_at"] = finished_at
            metadata["tracker_error"] = str(exc)
        else:
            metadata["tracker_error"] = None
        metadata["pipeline_error"] = str(exc)
        metadata["final_output_ready"] = False

    write_json(run_dir / "metadata.json", metadata)


def build_frame_output(
    frame_index: int,
    frame_file: str,
    timestamp_ms: int,
    sgg_out: Any,
    apf_out: Any,
    vehicle: VehicleState,
) -> dict[str, Any]:
    top_entity = next(
        (
            entity
            for entity in sorted(
                (entity for entity in sgg_out.nodes if not entity.is_ego),
                key=lambda entity: (
                    entity.danger_quality,
                    -entity.ttc if entity.ttc != float("inf") else float("-inf"),
                ),
                reverse=True,
            )
        ),
        None,
    )

    danger_entities = [
        {
            "id": entity.id,
            "cls": entity.cls,
            "dangerQuality": entity.danger_quality,
            "dangerClass": entity.danger_class.value,
            "ttc": None if entity.ttc == float("inf") else entity.ttc,
        }
        for entity in sorted(
            (entity for entity in sgg_out.nodes if not entity.is_ego),
            key=lambda entity: entity.danger_quality,
            reverse=True,
        )[:5]
    ]

    primary_relationship = next(
        (
            relationship
            for relationship in sorted(
                sgg_out.relationships,
                key=lambda relationship: relationship.danger_modifier,
                reverse=True,
            )
            if relationship.danger_modifier > 0
        ),
        None,
    )

    if primary_relationship is not None:
        reasoning_summary = (
            primary_relationship.reasoning
            or f"{primary_relationship.semantic_label.value} increases danger by {primary_relationship.danger_modifier:+.2f}."
        )
        primary_relation_label = (
            primary_relationship.semantic_label.value if primary_relationship.semantic_label else None
        )
        source_entity_id = primary_relationship.source_id
        target_entity_id = primary_relationship.target_id
    elif top_entity is not None:
        ttc_suffix = "with no finite TTC" if top_entity.ttc == float("inf") else f"with TTC {top_entity.ttc:.2f}s"
        reasoning_summary = (
            f"Highest-risk entity is {top_entity.cls} #{top_entity.id} "
            f"with danger quality {top_entity.danger_quality:.2f} ({top_entity.danger_class.value}, {ttc_suffix})."
        )
        primary_relation_label = None
        source_entity_id = 0
        target_entity_id = top_entity.id
    else:
        reasoning_summary = "No non-ego entities were available after pipeline processing."
        primary_relation_label = None
        source_entity_id = 0
        target_entity_id = 0

    apf_visual_data = apf_out.visual_data.model_dump() if apf_out.visual_data else {}
    sgg_visual_data = sgg_out.visual_data.model_dump() if sgg_out.visual_data else {}

    return {
        "frameIndex": frame_index,
        "frameFile": frame_file,
        "timestampMs": timestamp_ms,
        "steering": {
            "deltaTheta": apf_out.steering.delta_theta,
            "controlSteerX": apf_visual_data.get("control_steer_x", 0.0),
            "controlSteerY": apf_visual_data.get("control_steer_y", 0.0),
        },
        "velocity": {
            "vTarget": apf_out.velocity.v_target,
            "egoV": apf_visual_data.get("ego_v", vehicle.v_current),
        },
        "dangerZone": {
            "topEntity": None
            if top_entity is None
            else {
                "id": top_entity.id,
                "cls": top_entity.cls,
                "dangerQuality": top_entity.danger_quality,
                "dangerClass": top_entity.danger_class.value,
                "ttc": None if top_entity.ttc == float("inf") else top_entity.ttc,
            },
            "entities": danger_entities,
        },
        "reasoning": {
            "summary": reasoning_summary,
            "primaryRelation": primary_relation_label,
            "sourceEntityId": source_entity_id,
            "targetEntityId": target_entity_id,
        },
        "sggVisualData": sgg_visual_data,
        "apfVisualData": apf_visual_data,
    }



def build_run_final_output(run_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    run_dir = get_run_dir(run_id)
    tracker_dir = run_dir / "tracker"
    csv_files = sorted(tracker_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError("No tracker CSV found for this run.")

    csv_path = csv_files[0]
    frame_names = metadata.get("file_names", [])
    if not frame_names:
        raise ValueError("No uploaded frame names are available for this run.")

    per_frame_entities = parse_tracker_csv(csv_path)
    sgg_service = SGGService()
    apf_service = APFService()

    grid_data = np.zeros((40, 40))
    grid_data[:, 28:] = 1.0
    crop_grid = CropOccupancyGrid(data=grid_data, resolution=0.5, origin_x=-5.0, origin_y=-2.0)

    frame_outputs: list[dict[str, Any]] = []
    for frame_index, frame_file in enumerate(frame_names):
        kinematics = per_frame_entities.get(frame_index, [])
        semantics = infer_semantics(kinematics, _sgg_inference_cfg)
        sgg_out = sgg_service.process(kinematics, semantics, ego_vy=3.0, render_viz=True)

        vehicle = VehicleState(x=0.0, y=0.0, v_current=3.0, heading=0.0)
        apf_out = apf_service.compute(sgg_out.nodes, crop_grid, vehicle, render_viz=True)

        frame_outputs.append(
            build_frame_output(
                frame_index=frame_index,
                frame_file=frame_file,
                timestamp_ms=int(round(frame_index * (1000.0 / DEFAULT_FPS))),
                sgg_out=sgg_out,
                apf_out=apf_out,
                vehicle=vehicle,
            )
        )

    return {
        "runId": run_id,
        "status": "completed",
        "sourceFrames": {
            "fileCount": metadata["file_count"],
            "fileNames": frame_names,
            "samplingFps": DEFAULT_FPS,
        },
        "tracker": {
            "status": metadata.get("tracker_status", "completed"),
            "startedAt": metadata.get("tracker_started_at"),
            "finishedAt": metadata.get("tracker_finished_at"),
            "error": metadata.get("tracker_error"),
            "csvPath": str(csv_path),
            "processedFrames": metadata.get("tracker_output", {}).get("processed_frames", 0),
        },
        "frames": frame_outputs,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sort_frame_names(name: str) -> tuple[str, str]:
    stem = Path(name).stem
    digits = "".join(character for character in stem if character.isdigit())
    return (digits.zfill(12) if digits else stem.lower(), name.lower())


# ---------------------------------------------------------------------------
# Live demo pipeline (uses agri_nav demo scene)
# ---------------------------------------------------------------------------


def _run_demo_pipeline() -> dict[str, Any]:
    """Run the full SGG → APF pipeline on the canonical demo scene."""
    from agri_nav.demo_scene import DEMO_KINEMATICS, EGO_VY, make_crop_grid

    # 1. Infer semantics from kinematics
    cfg = SGGInferenceConfig(ego_vy=EGO_VY)
    semantics = infer_semantics(DEMO_KINEMATICS, cfg)

    # 2. SGG processing (merge, classify, scene graph, viz)
    sgg_out = _sgg_service.process(
        DEMO_KINEMATICS, semantics, ego_vy=EGO_VY, render_viz=True,
    )

    # 3. APF control + viz
    crop_grid = make_crop_grid()
    vehicle = VehicleState(x=5.0, y=3.0, v_current=EGO_VY, heading=0.0)
    apf_out = _apf_service.compute(
        sgg_out.nodes, crop_grid, vehicle, render_viz=True,
    )

    result: dict[str, Any] = {"sggVisualData": {}, "apfVisualData": {}}
    if sgg_out.visual_data:
        result["sggVisualData"] = sgg_out.visual_data.model_dump()
    if apf_out.visual_data:
        result["apfVisualData"] = apf_out.visual_data.model_dump()
    return result
