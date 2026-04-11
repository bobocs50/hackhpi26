"""Dump complete mock SGGOutput and ControlOutput as JSON (full demo scene)."""
import json
import numpy as np
from agri_nav.dto.perception import KinematicsEntity, EntityType, CropOccupancyGrid
from agri_nav.dto.config import SGGConfig, APFConfig
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.logic.sgg_processor import (
    merge_perception, SceneRelationship, SemanticRelType,
    RelationshipType, SEMANTIC_DANGER_MODIFIERS,
)
from agri_nav.service.apf_service import APFService, VehicleState
from agri_nav.service.sgg_service import SGGService

OUT_DIR = r'C:\Users\b290\.gemini\antigravity\brain\0c729145-54fb-428e-9207-5f18bc7814ff'

# ── Full 7-entity demo scene (mirrors viz_sgg_graph._demo) ─────────────────
kins = [
    KinematicsEntity(id=1, cls='human', x=0.5, y=4.0, vx=-0.2, vy=-1.0,
                     detection_confidence=0.95, track_age=25),
    KinematicsEntity(id=2, cls='tractor', x=-3.0, y=8.0, vx=0.0, vy=-0.5,
                     detection_confidence=0.80, track_age=40),
    KinematicsEntity(id=3, cls='bush', x=2.0, y=3.0, vx=0.0, vy=0.0,
                     detection_confidence=0.70, track_age=60),
    KinematicsEntity(id=4, cls='deer', x=-1.0, y=6.0, vx=0.8, vy=-0.3,
                     detection_confidence=0.85, track_age=8),
    KinematicsEntity(id=5, cls='post', x=3.5, y=7.0, vx=0.0, vy=0.0,
                     detection_confidence=0.90, track_age=100),
    KinematicsEntity(id=6, cls='dog', x=1.0, y=5.5, vx=-0.5, vy=-0.8,
                     detection_confidence=0.88, track_age=15),
    KinematicsEntity(id=7, cls='crop', x=4.0, y=5.0, vx=0.0, vy=0.0,
                     detection_confidence=0.60, track_age=100,
                     entity_type=EntityType.AREA, extent_x=2.0, extent_y=3.0),
]

ego_vy = 3.0
inf_cfg = SGGInferenceConfig(ego_vy=ego_vy)
sems = infer_semantics(kins, inf_cfg)

# External entity-to-entity SGG relationships
entity_rels = [
    SceneRelationship(
        source_id=1, target_id=6,
        relation=RelationshipType.NEAR, distance=1.5,
        semantic_label=SemanticRelType.FOLLOWING,
        danger_modifier=SEMANTIC_DANGER_MODIFIERS[SemanticRelType.FOLLOWING]
    ),
    SceneRelationship(
        source_id=6, target_id=1,
        relation=RelationshipType.NEAR, distance=1.5,
        semantic_label=SemanticRelType.MOVING_AWAY,
        danger_modifier=SEMANTIC_DANGER_MODIFIERS[SemanticRelType.MOVING_AWAY]
    ),
    SceneRelationship(
        source_id=2, target_id=3,
        relation=RelationshipType.NEAR, distance=7.0,
        semantic_label=SemanticRelType.CROSSING,
        danger_modifier=SEMANTIC_DANGER_MODIFIERS[SemanticRelType.CROSSING]
    ),
]

# ── SGGOutput (complete) ──────────────────────────────────────────────────
sgg_svc = SGGService(SGGConfig())
sgg_out = sgg_svc.process(
    kinematics=kins, semantics=sems,
    entity_sgg_rels=entity_rels,
    ego_vy=ego_vy, render_viz=True
)

sgg_dict = {
    "nodes": [n.model_dump() for n in sgg_out.nodes],
    "relationships": [r.model_dump() for r in sgg_out.relationships],
    "visual_data": sgg_out.visual_data.model_dump() if sgg_out.visual_data else None,
}
with open(f'{OUT_DIR}\\sgg_output_complete.json', 'w') as f:
    json.dump(sgg_dict, f, indent=2, default=str)

# ── ControlOutput (complete) ──────────────────────────────────────────────
apf_cfg = APFConfig()
vehicle = VehicleState(x=0.0, y=0.0, v_current=ego_vy, heading=0.0)
tracked = merge_perception(kins, sems, SGGConfig(), ego_vy=vehicle.v_current)
crop_grid = CropOccupancyGrid(
    data=np.zeros((40, 40)), resolution=0.5, origin_x=-5.0, origin_y=-2.0
)
# Populate crop zone
crop_grid.data[:, 28:] = 1.0

apf_svc = APFService(apf_cfg)
apf_out = apf_svc.compute(tracked, crop_grid, vehicle, render_viz=True)

apf_dict = {
    "steering": apf_out.steering.model_dump(),
    "velocity": apf_out.velocity.model_dump(),
    "visual_data": apf_out.visual_data.model_dump() if apf_out.visual_data else None,
}
with open(f'{OUT_DIR}\\apf_output_complete.json', 'w') as f:
    json.dump(apf_dict, f, indent=2, default=str)

print('Done — wrote sgg_output_complete.json and apf_output_complete.json')
