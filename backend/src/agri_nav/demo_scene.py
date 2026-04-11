"""Canonical demo scene used by all visualization demos and dump_samples.

Defines a 6-entity agricultural scenario observed by a harvester (ego)
driving forward at 3 m/s through a crop field:

  id=1  human  — field worker walking towards the machine (handler)
  id=4  mud    — stationary terrain hazard on the left
  id=5  post   — stationary fence post off to the right
  id=6  dog    — moving animal near the human (on leash)
  id=7  deer   — grazing animal further ahead, very slow
  id=8  bush   — stationary vegetation cluster ahead-right

Import from here instead of duplicating entity definitions in every
demo / visualization module.
"""

from __future__ import annotations

import numpy as np

from agri_nav.dto.perception import CropOccupancyGrid, EntityType, KinematicsEntity


# ---------------------------------------------------------------------------
# Ego configuration
# ---------------------------------------------------------------------------

EGO_VY: float = 3.0
"""Nominal ego forward velocity [m/s]."""


# ---------------------------------------------------------------------------
# Detected entities (YOLOv10 + ByteTrack output)
# ---------------------------------------------------------------------------

DEMO_KINEMATICS: list[KinematicsEntity] = [
    # Human walking towards machine — field worker / handler
    KinematicsEntity(
        id=1, cls="human", x=0.5, y=4.0, vx=-0.2, vy=-1.0,
        detection_confidence=0.95, track_age=25,
    ),
    # Mud patch — stationary terrain hazard
    KinematicsEntity(
        id=4, cls="mud", x=-1.0, y=6.0, vx=0.0, vy=0.0,
        detection_confidence=0.85, track_age=8,
    ),
    # Fence post — permanent static infrastructure
    KinematicsEntity(
        id=5, cls="post", x=3.5, y=7.0, vx=0.0, vy=0.0,
        detection_confidence=0.90, track_age=100,
    ),
    # Dog near the human — moving with handler, possibly on leash
    KinematicsEntity(
        id=6, cls="dog", x=1.0, y=5.5, vx=-0.5, vy=-0.8,
        detection_confidence=0.88, track_age=15,
    ),
    # Deer grazing ahead — slow, calm, but alive
    KinematicsEntity(
        id=7, cls="deer", x=-0.5, y=9.0, vx=0.05, vy=-0.05,
        detection_confidence=0.80, track_age=40,
    ),
    # Bush cluster — static vegetation near the crop edge
    KinematicsEntity(
        id=8, cls="bush", x=2.5, y=8.5, vx=0.0, vy=0.0,
        detection_confidence=0.75, track_age=60,
    ),
]

# Subset without *area* entities (for graph-only demos)
DEMO_KINEMATICS_POINT_ONLY: list[KinematicsEntity] = [
    k for k in DEMO_KINEMATICS if k.entity_type != EntityType.AREA
]


# ---------------------------------------------------------------------------
# Crop occupancy grid
# ---------------------------------------------------------------------------

def make_crop_grid() -> CropOccupancyGrid:
    """40×40 grid with a crop zone on the right side (columns 28+)."""
    data = np.zeros((40, 40))
    data[:, 28:] = 1.0
    return CropOccupancyGrid(
        data=data, resolution=0.5, origin_x=-5.0, origin_y=-2.0,
    )
