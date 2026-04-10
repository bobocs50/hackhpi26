"""Pydantic models for upstream perception data (ROS2 topic payloads)."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class DangerClass(str, Enum):
    """Classification of an entity's threat level for APF field profiling.

    Improvement #6: different field profiles per class instead of
    treating every entity identically.
    """

    CROSSABLE = "crossable"
    MUST_AVOID = "must_avoid"
    TARGET = "target"


class EntityType(str, Enum):
    """Whether an entity is a discrete object or covers an area."""

    POINT = "point"
    AREA = "area"


class HomogeneousCoord(BaseModel):
    """2-D homogeneous coordinate [x, y, w].

    Convention: left of ego = negative x, right = positive x.
    ``w = 1.0`` for Euclidean points; ``w = 0`` for direction vectors.
    """

    model_config = ConfigDict(frozen=True)

    x: float
    y: float
    w: float = 1.0

    def to_euclidean(self) -> tuple[float, float]:
        """Project back to Euclidean (x/w, y/w).  Raises if w ≈ 0."""
        if abs(self.w) < 1e-12:
            raise ValueError("Cannot project direction vector (w≈0) to Euclidean")
        return self.x / self.w, self.y / self.w


class KinematicsEntity(BaseModel):
    """Single tracked dynamic entity from YOLOv10 + ByteTrack.

    Coordinates are in the vehicle-local homogeneous frame:
    x = lateral (negative = left, positive = right), y = forward.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    cls: str = Field(description="Detected object class label")
    x: float = Field(description="Lateral position [m] (left<0, right>0)")
    y: float = Field(description="Forward position [m]")
    vx: float = Field(description="Lateral velocity [m/s]")
    vy: float = Field(description="Forward velocity [m/s]")
    detection_confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.9, description="YOLO detection confidence"
    )
    track_age: int = Field(
        default=10, ge=0, description="ByteTrack track age in frames"
    )
    entity_type: EntityType = Field(
        default=EntityType.POINT,
        description="POINT for discrete objects, AREA for zones (e.g. crops)",
    )
    extent_x: float = Field(
        default=0.0, ge=0.0,
        description="Half-width of the area entity [m] (0 for point entities)",
    )
    extent_y: float = Field(
        default=0.0, ge=0.0,
        description="Half-depth of the area entity [m] (0 for point entities)",
    )

    @property
    def homogeneous(self) -> HomogeneousCoord:
        """Return position as a homogeneous coordinate [x, y, 1]."""
        return HomogeneousCoord(x=self.x, y=self.y, w=1.0)


class SemanticEntity(BaseModel):
    """Semantic graph attributes for a tracked entity (from TensorRT SGG).

    ``certainty`` and ``danger_quality`` are in [0, 1].
    """

    model_config = ConfigDict(frozen=True)

    id: int
    certainty: Annotated[float, Field(ge=0.0, le=1.0)]
    danger_quality: Annotated[float, Field(ge=0.0, le=1.0)]


class CropOccupancyGrid(BaseModel):
    """2-D semantic probability grid P_crop(x, y).

    ``data`` is a 2-D NumPy array where each cell holds a probability [0, 1].
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    data: np.ndarray = Field(description="2-D probability grid")
    resolution: float = Field(
        gt=0.0, description="Meters per grid cell"
    )
    origin_x: float = Field(
        description="World x-coordinate of grid cell (0, 0)"
    )
    origin_y: float = Field(
        description="World y-coordinate of grid cell (0, 0)"
    )
