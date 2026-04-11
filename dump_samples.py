"""Dump complete mock SGGOutput and ControlOutput as JSON (full demo scene)."""

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from agri_nav.demo_scene import DEMO_KINEMATICS, EGO_VY, make_crop_grid
from agri_nav.dto.config import APFConfig, SGGConfig
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.logic.sgg_processor import merge_perception
from agri_nav.service.apf_service import APFService, VehicleState
from agri_nav.service.sgg_service import SGGService

logger = logging.getLogger(__name__)

def main(out_dir: Path) -> None:
    """Generate sample JSON outputs for the SGG and APF pipelines."""
    out_dir.mkdir(parents=True, exist_ok=True)

    kins = DEMO_KINEMATICS
    inf_cfg = SGGInferenceConfig(ego_vy=EGO_VY)
    sems = infer_semantics(kins, inf_cfg)

    # ── SGGOutput (complete — uses mock SGG automatically) ────────────────────
    sgg_svc = SGGService(SGGConfig())
    sgg_out = sgg_svc.process(
        kinematics=kins, semantics=sems,
        ego_vy=EGO_VY, render_viz=True,
    )

    sgg_dict = {
        "nodes": [n.model_dump() for n in sgg_out.nodes],
        "relationships": [r.model_dump() for r in sgg_out.relationships],
        "visual_data": sgg_out.visual_data.model_dump() if sgg_out.visual_data else None,
    }
    sgg_path = out_dir / "sgg_output_complete.json"
    sgg_path.write_text(json.dumps(sgg_dict, indent=2, default=str))

    # ── ControlOutput (complete) ──────────────────────────────────────────────
    apf_cfg = APFConfig()
    vehicle = VehicleState(x=0.0, y=0.0, v_current=EGO_VY, heading=0.0)
    tracked = merge_perception(kins, sems, SGGConfig(), ego_vy=vehicle.v_current)
    crop_grid = make_crop_grid()

    apf_svc = APFService(apf_cfg)
    apf_out = apf_svc.compute(tracked, crop_grid, vehicle, render_viz=True)

    apf_dict = {
        "steering": apf_out.steering.model_dump(),
        "velocity": apf_out.velocity.model_dump(),
        "visual_data": apf_out.visual_data.model_dump() if apf_out.visual_data else None,
    }
    apf_path = out_dir / "apf_output_complete.json"
    apf_path.write_text(json.dumps(apf_dict, indent=2, default=str))

    logger.info("Wrote %s and %s", sgg_path, apf_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Dump sample SGG/APF JSON outputs")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write JSON files into (default: ./output)",
    )
    main(parser.parse_args().out_dir)
