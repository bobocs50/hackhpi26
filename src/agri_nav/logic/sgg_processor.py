"""SGG entity processing — pure functions.

Handles danger classification, temporal certainty smoothing, and
merging kinematics with semantic data into tracked entities.
The scene graph includes the ego vehicle as a node (id=0).
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from agri_nav.dto.config import SGGConfig
from agri_nav.dto.perception import (
    DangerClass,
    EntityType,
    HomogeneousCoord,
    KinematicsEntity,
    SemanticEntity,
)


# -- Constants ---------------------------------------------------------------

EGO_ID: int = 0
"""Reserved entity ID for the ego vehicle."""


# ---------------------------------------------------------------------------
# Relationship types for the scene graph
# ---------------------------------------------------------------------------


class RelationshipType(str, Enum):
    """Spatial relationship labels between two tracked entities."""

    NEAR = "near"
    HEADING_TOWARDS = "heading_towards"
    SAME_LANE = "same_lane"


class SemanticRelType(str, Enum):
    """Semantic relationship labels from the upstream SGG model.

    Each relationship carries a danger modifier that adjusts the
    danger_quality of the connected entities when the graph is collapsed.
    """

    BLOCKING_PATH = "blocking_path"       # +0.3  entity is in the way
    FOLLOWING = "following"               # +0.15 entity tailing ego
    CROSSING = "crossing"                 # +0.25 entity cutting across
    MOVING_AWAY = "moving_away"           # -0.2  entity leaving
    STATIONARY_SAFE = "stationary_safe"   # -0.15 static, non-threatening
    OCCLUDING = "occluding"               # +0.1  hiding something behind it


# Danger modifier lookup: positive = increases danger, negative = decreases
SEMANTIC_DANGER_MODIFIERS: dict[SemanticRelType, float] = {
    SemanticRelType.BLOCKING_PATH: +0.30,
    SemanticRelType.FOLLOWING: +0.15,
    SemanticRelType.CROSSING: +0.25,
    SemanticRelType.MOVING_AWAY: -0.20,
    SemanticRelType.STATIONARY_SAFE: -0.15,
    SemanticRelType.OCCLUDING: +0.10,
}


class SceneRelationship(BaseModel):
    """A directed edge in the scene graph."""

    model_config = ConfigDict(frozen=True)

    source_id: int
    target_id: int
    relation: RelationshipType
    distance: float = Field(ge=0.0, description="Euclidean distance [m]")
    ttc: float | None = Field(
        default=None, description="Time-to-collision [s] (None if not applicable)"
    )
    semantic_label: SemanticRelType | None = Field(
        default=None,
        description="Semantic relationship from upstream SGG (None = spatial only)",
    )
    danger_modifier: float = Field(
        default=0.0,
        description="Danger adjustment: positive increases, negative decreases danger",
    )


# ---------------------------------------------------------------------------
# Merged entity DTO (output of the SGG processing pipeline)
# ---------------------------------------------------------------------------


class TrackedEntity(BaseModel):
    """A fully-merged, classified entity ready for APF consumption."""

    model_config = ConfigDict(frozen=True)

    id: int
    cls: str
    x: float
    y: float
    vx: float
    vy: float
    certainty: float = Field(ge=0.0, le=1.0)
    danger_quality: float = Field(ge=0.0, le=1.0)
    danger_class: DangerClass
    smoothed_certainty: float = Field(ge=0.0, le=1.0)

    # -- New fields --
    is_ego: bool = Field(default=False, description="True for the ego-vehicle node")
    ttc: float = Field(
        default=float("inf"),
        ge=0.0,
        description="Time-to-collision with ego [s]",
    )
    entity_type: EntityType = Field(default=EntityType.POINT)
    extent_x: float = Field(
        default=0.0, ge=0.0,
        description="Half-width for area entities [m]",
    )
    extent_y: float = Field(
        default=0.0, ge=0.0,
        description="Half-depth for area entities [m]",
    )

    @property
    def homogeneous(self) -> HomogeneousCoord:
        """Return position as a homogeneous coordinate [x, y, 1]."""
        return HomogeneousCoord(x=self.x, y=self.y, w=1.0)


class SGGOutput(BaseModel):
    """Combined output of the SGG inference pipeline."""

    model_config = ConfigDict(frozen=True)

    nodes: list[TrackedEntity]
    relationships: list[SceneRelationship]
    frontend_viz_json: str | None = Field(
        default=None,
        description="Serialized Plotly Figure JSON for UI rendering, if generated",
    )


def create_ego_entity(
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> TrackedEntity:
    """Factory for the ego-vehicle node (always at origin)."""
    return TrackedEntity(
        id=EGO_ID,
        cls="ego",
        x=0.0,
        y=0.0,
        vx=ego_vx,
        vy=ego_vy,
        certainty=1.0,
        danger_quality=0.0,
        danger_class=DangerClass.TARGET,
        smoothed_certainty=1.0,
        is_ego=True,
        ttc=float("inf"),
        entity_type=EntityType.POINT,
    )


# ---------------------------------------------------------------------------
# Classification (improvement #6)
# ---------------------------------------------------------------------------


def classify_danger(
    danger_quality: float,
    thresholds: dict[DangerClass, float],
) -> DangerClass:
    """Map a danger_quality scalar to a discrete DangerClass.

    * q <= crossable_threshold  → CROSSABLE
    * q >= must_avoid_threshold → MUST_AVOID
    * else                      → TARGET
    """
    crossable_th = thresholds.get(DangerClass.CROSSABLE, 0.3)
    must_avoid_th = thresholds.get(DangerClass.MUST_AVOID, 0.7)

    if danger_quality <= crossable_th:
        return DangerClass.CROSSABLE
    if danger_quality >= must_avoid_th:
        return DangerClass.MUST_AVOID
    return DangerClass.TARGET


# ---------------------------------------------------------------------------
# Temporal smoothing (improvement #7)
# ---------------------------------------------------------------------------


def smooth_certainty(
    current: float,
    prev_smoothed: float,
    ema_alpha: float,
) -> float:
    """Exponential moving average (EMA) on certainty.

    smoothed = α · current + (1 − α) · prev_smoothed
    """
    return ema_alpha * current + (1.0 - ema_alpha) * prev_smoothed


# ---------------------------------------------------------------------------
# TTC computation (for scene-graph depth)
# ---------------------------------------------------------------------------


def _compute_ttc(
    x: float,
    y: float,
    vx: float,
    vy: float,
    ego_vx: float,
    ego_vy: float,
    epsilon: float = 0.1,
) -> float:
    """Compute time-to-collision with the ego vehicle at the origin."""
    dist = math.sqrt(x**2 + y**2)
    if dist < 1e-9:
        return 0.0
    rel_vx = vx - ego_vx
    rel_vy = vy - ego_vy
    ux, uy = -x / dist, -y / dist
    closing = rel_vx * ux + rel_vy * uy
    if closing <= 0:
        return float("inf")
    return dist / max(epsilon, closing)


# ---------------------------------------------------------------------------
# Merge perception streams
# ---------------------------------------------------------------------------


def merge_perception(
    kinematics: list[KinematicsEntity],
    semantics: list[SemanticEntity],
    config: SGGConfig,
    prev_smoothed: dict[int, float] | None = None,
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> list[TrackedEntity]:
    """Join kinematics + semantics by entity ID and apply SGG processing.

    Steps:
    1. Inner-join on ``id``.
    2. Classify each entity's danger (improvement #6).
    3. Apply EMA certainty smoothing (improvement #7).
    4. Compute TTC with the ego vehicle.

    Parameters
    ----------
    prev_smoothed:
        Mapping ``{entity_id: previous_smoothed_certainty}``.
        For entities not present, ``current`` certainty is used as seed.
    ego_vx, ego_vy:
        Ego vehicle velocity for TTC computation.

    Returns
    -------
    List of fully-populated ``TrackedEntity`` DTOs.
    """
    if prev_smoothed is None:
        prev_smoothed = {}

    semantics_by_id = {s.id: s for s in semantics}
    results: list[TrackedEntity] = []

    for kin in kinematics:
        sem = semantics_by_id.get(kin.id)
        if sem is None:
            continue  # no semantic data for this entity → skip

        danger_class = classify_danger(sem.danger_quality, config.danger_thresholds)
        smoothed = smooth_certainty(
            sem.certainty,
            prev_smoothed.get(kin.id, sem.certainty),
            config.ema_alpha,
        )
        ttc = _compute_ttc(kin.x, kin.y, kin.vx, kin.vy, ego_vx, ego_vy)

        results.append(
            TrackedEntity(
                id=kin.id,
                cls=kin.cls,
                x=kin.x,
                y=kin.y,
                vx=kin.vx,
                vy=kin.vy,
                certainty=sem.certainty,
                danger_quality=sem.danger_quality,
                danger_class=danger_class,
                smoothed_certainty=round(smoothed, 6),
                ttc=round(ttc, 4) if ttc != float("inf") else float("inf"),
                entity_type=kin.entity_type,
                extent_x=kin.extent_x,
                extent_y=kin.extent_y,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Scene graph construction (relationships between entities)
# ---------------------------------------------------------------------------


def build_scene_graph(
    entities: list[TrackedEntity],
    proximity_threshold: float = 8.0,
    lane_width: float = 1.5,
    include_ego: bool = True,
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> tuple[list[TrackedEntity], list[SceneRelationship]]:
    """Extract spatial relationships and optionally insert the ego node.

    Only point-type entities participate in the graph (area entities
    like crops are excluded because distance relationships are
    ill-defined for areas).  Area entities are still returned in the
    full entity list for APF force-field computation.

    Parameters
    ----------
    include_ego:
        If True, prepend an ego node (id=0) and create ego→entity edges
        with TTC as the depth metric.

    Returns
    -------
    (nodes, relationships) — the updated entity list and edge list.
    ``nodes`` includes only point entities + ego (no area entities).
    """
    # Only point entities participate in the graph
    nodes = [e for e in entities if e.entity_type != EntityType.AREA]

    # Insert ego node at origin
    if include_ego and not any(e.is_ego for e in nodes):
        nodes.insert(0, create_ego_entity(ego_vx, ego_vy))

    relationships: list[SceneRelationship] = []

    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx**2 + dy**2)

            if dist > proximity_threshold:
                continue

            # Compute TTC between this pair (directional)
            pair_ttc: float | None = None
            if a.is_ego:
                pair_ttc = b.ttc
            elif b.is_ego:
                pair_ttc = a.ttc

            # NEAR
            relationships.append(
                SceneRelationship(
                    source_id=a.id,
                    target_id=b.id,
                    relation=RelationshipType.NEAR,
                    distance=round(dist, 3),
                    ttc=round(pair_ttc, 3) if pair_ttc is not None and pair_ttc != float("inf") else pair_ttc,
                )
            )

            # HEADING_TOWARDS
            if dist > 0:
                dot_a = a.vx * dx + a.vy * dy
                if dot_a > 0:
                    relationships.append(
                        SceneRelationship(
                            source_id=a.id,
                            target_id=b.id,
                            relation=RelationshipType.HEADING_TOWARDS,
                            distance=round(dist, 3),
                            ttc=round(pair_ttc, 3) if pair_ttc is not None and pair_ttc != float("inf") else pair_ttc,
                        )
                    )
                dot_b = b.vx * (-dx) + b.vy * (-dy)
                if dot_b > 0:
                    relationships.append(
                        SceneRelationship(
                            source_id=b.id,
                            target_id=a.id,
                            relation=RelationshipType.HEADING_TOWARDS,
                            distance=round(dist, 3),
                            ttc=round(pair_ttc, 3) if pair_ttc is not None and pair_ttc != float("inf") else pair_ttc,
                        )
                    )

            # SAME_LANE
            if abs(dx) <= lane_width:
                relationships.append(
                    SceneRelationship(
                        source_id=a.id,
                        target_id=b.id,
                        relation=RelationshipType.SAME_LANE,
                        distance=round(dist, 3),
                        ttc=round(pair_ttc, 3) if pair_ttc is not None and pair_ttc != float("inf") else pair_ttc,
                    )
                )

    return nodes, relationships


# ---------------------------------------------------------------------------
# Semantic relationship inference & graph collapse
# ---------------------------------------------------------------------------


def infer_semantic_relations(
    entities: list[TrackedEntity],
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> list[SceneRelationship]:
    """Infer semantic relationships between ego and entities from kinematics.

    Uses velocity/position heuristics to assign high-level semantic labels
    (BLOCKING_PATH, CROSSING, MOVING_AWAY, STATIONARY_SAFE, FOLLOWING).
    These simulate what an upstream SGG model would produce.
    """
    ego_id = EGO_ID
    rels: list[SceneRelationship] = []

    for ent in entities:
        if ent.is_ego:
            continue

        dist = math.sqrt(ent.x**2 + ent.y**2)
        if dist < 1e-9:
            continue

        # Relative velocity towards ego
        rel_vx = ent.vx - ego_vx
        rel_vy = ent.vy - ego_vy
        ux, uy = -ent.x / dist, -ent.y / dist
        closing_speed = rel_vx * ux + rel_vy * uy

        # Lateral component of relative velocity
        lateral_speed = abs(rel_vx * (-uy) + rel_vy * ux)

        speed = math.sqrt(ent.vx**2 + ent.vy**2)

        # Classify the relationship
        if speed < 0.05:
            sem_type = SemanticRelType.STATIONARY_SAFE
        elif closing_speed > 1.0 and lateral_speed < 0.5:
            sem_type = SemanticRelType.BLOCKING_PATH
        elif lateral_speed > 0.8:
            sem_type = SemanticRelType.CROSSING
        elif closing_speed < -0.3:
            sem_type = SemanticRelType.MOVING_AWAY
        elif closing_speed > 0:
            sem_type = SemanticRelType.FOLLOWING
        else:
            sem_type = SemanticRelType.MOVING_AWAY

        modifier = SEMANTIC_DANGER_MODIFIERS[sem_type]

        rels.append(
            SceneRelationship(
                source_id=ego_id,
                target_id=ent.id,
                relation=RelationshipType.NEAR,
                distance=round(dist, 3),
                ttc=round(ent.ttc, 3) if ent.ttc != float("inf") else None,
                semantic_label=sem_type,
                danger_modifier=modifier,
            )
        )

    return rels


def collapse_semantic_graph(
    entities: list[TrackedEntity],
    semantic_rels: list[SceneRelationship],
) -> list[TrackedEntity]:
    """Apply semantic danger modifiers to collapse the relationship graph.

    For each entity, sum the danger_modifiers from all incoming semantic
    relationships and adjust danger_quality accordingly (clamped to [0, 1]).
    """
    modifier_sums: dict[int, float] = {}
    for rel in semantic_rels:
        if rel.semantic_label is not None:
            modifier_sums[rel.target_id] = (
                modifier_sums.get(rel.target_id, 0.0) + rel.danger_modifier
            )

    result: list[TrackedEntity] = []
    for ent in entities:
        mod = modifier_sums.get(ent.id, 0.0)
        if abs(mod) < 1e-9:
            result.append(ent)
        else:
            new_dq = max(0.0, min(1.0, ent.danger_quality + mod))
            result.append(
                TrackedEntity(
                    **{
                        **ent.model_dump(),
                        "danger_quality": round(new_dq, 6),
                    }
                )
            )

    return result
