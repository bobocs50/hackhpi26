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

from reporting import build_report_response, load_default_run
from yolo_tracker import run_yolo_tracker

# Add the project root so `agri_nav` package can be imported
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

import numpy as np
from agri_nav.dto.config import APFConfig, SGGConfig
from agri_nav.dto.perception import CropOccupancyGrid
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.mapper.tracker_csv import get_latest_frame_entities, parse_tracker_csv
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
        "created_at": created_at,
        "updated_at": created_at,
        "pipeline_started_at": created_at,
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
    """Run the full SGG → APF pipeline on tracker output and return visual data.

    Returns ``MockVisualDataResponse`` compatible JSON with
    ``sggVisualData`` and ``apfVisualData`` keys.
    """
    metadata = load_run_metadata_or_404(run_id)

    if metadata.get("tracker_status") != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Tracker has not finished. Status: {metadata.get('tracker_status')}",
        )

    # Find the tracker CSV
    run_dir = get_run_dir(run_id)
    tracker_dir = run_dir / "tracker"
    csv_files = list(tracker_dir.glob("*.csv"))
    if not csv_files:
        raise HTTPException(status_code=404, detail="No tracker CSV found for this run.")
    csv_path = csv_files[0]

    # Parse tracker CSV → KinematicsEntity (last frame)
    kinematics = get_latest_frame_entities(csv_path)
    if not kinematics:
        raise HTTPException(status_code=404, detail="No entities detected in tracker output.")

    # Infer semantics (certainty + danger_quality via TTC heuristics)
    semantics = infer_semantics(kinematics, _sgg_inference_cfg)

    # Run SGG pipeline (merge, classify, build scene graph, viz)
    sgg_out = _sgg_service.process(kinematics, semantics, ego_vy=3.0, render_viz=True)

    # Build a synthetic crop grid (uniform field for demo)
    grid_data = np.ones((20, 20))
    grid_data[:, 14:] = 0.0  # crop edge at column 14
    crop_grid = CropOccupancyGrid(data=grid_data, resolution=0.5, origin_x=0.0, origin_y=0.0)

    # Run APF pipeline
    vehicle = VehicleState(x=5.0, y=3.0, v_current=3.0, heading=0.0)
    apf_out = _apf_service.compute(sgg_out.nodes, crop_grid, vehicle, render_viz=True)

    # Assemble frontend-compatible response
    response: dict[str, Any] = {"sggVisualData": {}, "apfVisualData": {}}

    if sgg_out.visual_data:
        response["sggVisualData"] = sgg_out.visual_data.model_dump()

    if apf_out.visual_data:
        response["apfVisualData"] = apf_out.visual_data.model_dump()

    return response


def get_run_dir(run_id: str) -> Path:
    return UPLOADS_DIR / run_id


def load_run_metadata_or_404(run_id: str) -> dict[str, Any]:
    metadata_path = get_run_dir(run_id) / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Run not found.")

    return read_json(metadata_path)


def run_tracker_for_run(run_id: str) -> None:
    run_dir = get_run_dir(run_id)
    metadata = load_run_metadata_or_404(run_id)

    try:
        tracker_output = run_yolo_tracker(run_dir, run_dir / "tracker")
        finished_at = utc_now_iso()
        metadata["status"] = "completed"
        metadata["updated_at"] = finished_at
        metadata["tracker_status"] = "completed"
        metadata["tracker_finished_at"] = finished_at
        metadata["tracker_error"] = None
        metadata["tracker_output"] = tracker_output
    except Exception as exc:
        finished_at = utc_now_iso()
        metadata["status"] = "failed"
        metadata["updated_at"] = finished_at
        metadata["tracker_status"] = "failed"
        metadata["tracker_finished_at"] = finished_at
        metadata["tracker_error"] = str(exc)

    write_json(run_dir / "metadata.json", metadata)


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
