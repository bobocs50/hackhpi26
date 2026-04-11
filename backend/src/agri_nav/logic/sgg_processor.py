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
from agri_nav.logic.sgg_inference import compute_ttc
from agri_nav.dto.visualization import MockSGGVisualData, SGGVisualData


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

    Labels are designed for an agricultural-machine ego context.
    """

    # --- Motion-based (kinematic) ---
    BLOCKING_PATH = "blocking_path"       # +0.30  entity is in the way
    FOLLOWING = "following"               # +0.15  entity tailing ego
    CROSSING = "crossing"                 # +0.25  entity cutting across
    MOVING_AWAY = "moving_away"           # -0.20  entity leaving
    STATIONARY_SAFE = "stationary_safe"   # -0.15  static, non-threatening
    OCCLUDING = "occluding"               # +0.10  hiding something behind it

    # --- Agricultural / semantic context ---
    HOLDING_LEASH = "holding_leash"       # +0.20  human controls an animal → animal more predictable but pair blocks more
    FLEEING_FROM = "fleeing_from"         # +0.15  animal startled by machine noise → erratic path
    TERRAIN_HAZARD = "terrain_hazard"     # +0.10  entity near hazardous ground (mud, ditch)
    SHELTERING_BEHIND = "sheltering_behind"  # +0.15  animal hiding behind obstacle → surprise emergence risk
    GRAZING = "grazing"                   # -0.10  animal is calm/feeding → low dynamic risk


# Danger modifier lookup: positive = increases danger, negative = decreases
SEMANTIC_DANGER_MODIFIERS: dict[SemanticRelType, float] = {
    SemanticRelType.BLOCKING_PATH: +0.30,
    SemanticRelType.FOLLOWING: +0.15,
    SemanticRelType.CROSSING: +0.25,
    SemanticRelType.MOVING_AWAY: -0.20,
    SemanticRelType.STATIONARY_SAFE: -0.15,
    SemanticRelType.OCCLUDING: +0.10,
    SemanticRelType.HOLDING_LEASH: +0.20,
    SemanticRelType.FLEEING_FROM: +0.15,
    SemanticRelType.TERRAIN_HAZARD: +0.10,
    SemanticRelType.SHELTERING_BEHIND: +0.15,
    SemanticRelType.GRAZING: -0.10,
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
    reasoning: str = Field(
        default="",
        description="LLM-generated reasoning for the danger score assignment",
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
    visual_data: SGGVisualData | None = Field(
        default=None,
        description="Structured data payload for frontend rendering, if generated",
    )
    initial_graph_viz: MockSGGVisualData | None = Field(
        default=None,
        description="Visualization of the initial mock SGG before collapse",
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
        ttc = compute_ttc(kin.x, kin.y, kin.vx, kin.vy, ego_vx, ego_vy, epsilon=0.1)

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


def mock_llm_evaluate_danger(
    source_cls: str, target_cls: str, sem_type: SemanticRelType, speed: float, closing_speed: float
) -> tuple[float, str]:
    """Mock LLM structured evaluation of entity-level danger.

    Produces a (danger_contribution, reasoning) pair that simulates what
    a vision-language model would output given the agricultural-machine
    ego context.  The reasoning references concrete field scenarios.
    """
    modifier = SEMANTIC_DANGER_MODIFIERS[sem_type]

    _reasoning: dict[SemanticRelType, str] = {
        SemanticRelType.BLOCKING_PATH: (
            f"The {target_cls} is directly ahead of {source_cls} and closing at "
            f"{closing_speed:.1f} m/s — the harvester must slow or steer around."
        ),
        SemanticRelType.CROSSING: (
            f"The {target_cls} is cutting laterally across the {source_cls}'s path "
            f"at {speed:.1f} m/s — collision risk if the machine does not yield."
        ),
        SemanticRelType.FOLLOWING: (
            f"The {target_cls} is trailing {source_cls}; if the machine brakes "
            f"suddenly the {target_cls} may not react in time."
        ),
        SemanticRelType.MOVING_AWAY: (
            f"The {target_cls} is moving away from {source_cls} "
            f"(closing {closing_speed:.1f} m/s), reducing collision risk."
        ),
        SemanticRelType.STATIONARY_SAFE: (
            f"The {target_cls} is stationary and not in the active working lane, "
            f"posing minimal dynamic risk to {source_cls}."
        ),
        SemanticRelType.OCCLUDING: (
            f"The {target_cls} is between {source_cls} and the machine, potentially "
            f"hiding {source_cls} from the perception system — surprise emergence risk."
        ),
        SemanticRelType.HOLDING_LEASH: (
            f"The {source_cls} appears to be controlling the {target_cls} (handler/leash). "
            f"The pair moves as a unit, increasing the combined footprint that blocks "
            f"the machine's path."
        ),
        SemanticRelType.FLEEING_FROM: (
            f"The {source_cls} is fleeing at {speed:.1f} m/s, likely startled by machine "
            f"noise or vibrations — its trajectory is erratic and hard to predict."
        ),
        SemanticRelType.TERRAIN_HAZARD: (
            f"The {source_cls} is near {target_cls} (hazardous terrain). If the "
            f"machine enters this zone it risks getting stuck or damaging the field."
        ),
        SemanticRelType.SHELTERING_BEHIND: (
            f"The {source_cls} is sheltering behind the {target_cls} — it may "
            f"emerge suddenly into the machine's path when startled."
        ),
        SemanticRelType.GRAZING: (
            f"The {target_cls} is calmly grazing at {speed:.1f} m/s and unlikely "
            f"to make sudden movements, but the machine should still give a wide berth."
        ),
    }

    reasoning = _reasoning.get(
        sem_type, f"The {target_cls} presents a generic hazard to {source_cls}."
    )
    return modifier, reasoning


def infer_semantic_relations(
    entities: list[TrackedEntity],
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> list[SceneRelationship]:
    """Infer semantic relationships between ego and entities from kinematics.

    Uses velocity/position heuristics combined with entity-class knowledge
    to assign semantic labels relevant to an agricultural machine context.
    """
    _TERRAIN = {"mud", "ditch", "puddle", "water"}
    _ANIMALS = {"dog", "deer", "animal", "cat", "bird"}

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

        # --- Agricultural semantic rules ---
        # Terrain hazards directly ahead
        if ent.cls in _TERRAIN:
            sem_type = SemanticRelType.TERRAIN_HAZARD
        # Fast animal fleeing from the machine
        elif ent.cls in _ANIMALS and speed > 0.5 and closing_speed > 0.3:
            sem_type = SemanticRelType.FLEEING_FROM
        # Slow animal grazing
        elif ent.cls in _ANIMALS and speed < 0.15:
            sem_type = SemanticRelType.GRAZING
        # --- Kinematic fallback ---
        elif speed < 0.05:
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


def mock_sgg_entity_graph(
    entities: list[TrackedEntity],
    proximity_threshold: float = 10.0,
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> list[SceneRelationship]:
    """Mock the output of a Scene Graph Generation model.

    A real SGG (e.g. Neural Motifs, VCTree, GPSNet) would produce
    entity-to-entity semantic relationships from visual features.
    Since no working SGG model was available without dependency conflicts,
    this function **simulates** that step using kinematic heuristics
    between every pair of non-ego entities.

    For each pair (A, B) within ``proximity_threshold``, it infers a
    directional semantic label based on their relative motion:

    * **BLOCKING_PATH** — B is ahead of A and closing in.
    * **CROSSING** — B has high lateral speed relative to A.
    * **FOLLOWING** — B is behind A and moving in the same direction.
    * **MOVING_AWAY** — B is receding from A.
    * **STATIONARY_SAFE** — B is stationary.
    * **OCCLUDING** — B is between A and the ego, partially hiding A.

    Returns
    -------
    Entity-to-entity ``SceneRelationship`` edges (no ego edges).
    """
    rels: list[SceneRelationship] = []
    non_ego = [e for e in entities if not e.is_ego]

    for i, a in enumerate(non_ego):
        for b in non_ego[i + 1:]:
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx**2 + dy**2)
            if dist < 1e-9 or dist > proximity_threshold:
                continue

            # Unit vector from A → B
            ux, uy = dx / dist, dy / dist

            # --- Classify A → B relationship ---
            ab_label = _classify_pair(a, b, ux, uy, dist, ego_vx, ego_vy)
            ab_score, ab_reasoning = mock_llm_evaluate_danger(
                a.cls, b.cls, ab_label,
                math.sqrt(b.vx**2 + b.vy**2),
                _closing_speed(a, b, ux, uy),
            )
            rels.append(SceneRelationship(
                source_id=a.id,
                target_id=b.id,
                relation=RelationshipType.NEAR,
                distance=round(dist, 3),
                semantic_label=ab_label,
                danger_modifier=ab_score,
                reasoning=ab_reasoning,
            ))

            # --- Classify B → A relationship ---
            ba_label = _classify_pair(b, a, -ux, -uy, dist, ego_vx, ego_vy)
            ba_score, ba_reasoning = mock_llm_evaluate_danger(
                b.cls, a.cls, ba_label,
                math.sqrt(a.vx**2 + a.vy**2),
                _closing_speed(b, a, -ux, -uy),
            )
            rels.append(SceneRelationship(
                source_id=b.id,
                target_id=a.id,
                relation=RelationshipType.NEAR,
                distance=round(dist, 3),
                semantic_label=ba_label,
                danger_modifier=ba_score,
                reasoning=ba_reasoning,
            ))

    return rels


def _closing_speed(
    src: TrackedEntity, tgt: TrackedEntity, ux: float, uy: float
) -> float:
    """Relative closing speed of *tgt* towards *src* along the connecting axis."""
    rel_vx = tgt.vx - src.vx
    rel_vy = tgt.vy - src.vy
    return -(rel_vx * ux + rel_vy * uy)


def _classify_pair(
    src: TrackedEntity,
    tgt: TrackedEntity,
    ux: float,
    uy: float,
    dist: float,
    ego_vx: float,
    ego_vy: float,
) -> SemanticRelType:
    """Classify the semantic relationship src → tgt in an agricultural context.

    *ux, uy* is the unit vector from src to tgt.

    The classifier combines kinematic cues with entity-class knowledge
    to produce relations meaningful for an agricultural machine:

    * A human near an animal → HOLDING_LEASH (handler controlling animal).
    * A fast-moving animal with the ego approaching → FLEEING_FROM.
    * An entity near mud/ditch terrain → TERRAIN_HAZARD (slip / stuck risk).
    * A slow animal near a stationary obstacle → SHELTERING_BEHIND.
    * A very slow animal → GRAZING (calm, low dynamic risk).
    * Otherwise falls back to kinematic classification (BLOCKING_PATH,
      CROSSING, FOLLOWING, MOVING_AWAY, STATIONARY_SAFE, OCCLUDING).
    """
    _ANIMALS = {"dog", "deer", "animal", "cat", "bird"}
    _HUMANS = {"human", "person", "child"}
    _TERRAIN = {"mud", "ditch", "puddle", "water"}
    _OBSTACLES = {"post", "rock", "cone", "bush", "tree", "fence"}

    rel_vx = tgt.vx - src.vx
    rel_vy = tgt.vy - src.vy
    closing = -(rel_vx * ux + rel_vy * uy)
    lateral = abs(-rel_vx * uy + rel_vy * ux)
    tgt_speed = math.sqrt(tgt.vx**2 + tgt.vy**2)
    src_speed = math.sqrt(src.vx**2 + src.vy**2)

    # --- Agricultural semantic rules (checked first) ---

    # Human near animal → handler / leash holder
    if src.cls in _HUMANS and tgt.cls in _ANIMALS and dist < 3.0:
        return SemanticRelType.HOLDING_LEASH

    # Animal near human → the animal is being held
    if src.cls in _ANIMALS and tgt.cls in _HUMANS and dist < 3.0:
        return SemanticRelType.HOLDING_LEASH

    # Fast-moving animal with ego approaching from behind → fleeing from machine noise
    if src.cls in _ANIMALS and tgt_speed < 0.1 and src_speed > 0.8:
        # src is an animal running; check if ego is roughly behind src
        src_ego_dist = math.sqrt(src.x**2 + src.y**2)
        if src_ego_dist < 8.0:
            return SemanticRelType.FLEEING_FROM

    # Entity near terrain hazard (mud, ditch) → terrain risk
    if tgt.cls in _TERRAIN and dist < 3.0:
        return SemanticRelType.TERRAIN_HAZARD
    if src.cls in _TERRAIN and dist < 3.0:
        return SemanticRelType.TERRAIN_HAZARD

    # Slow animal sheltering behind a stationary obstacle
    if src.cls in _ANIMALS and tgt.cls in _OBSTACLES and tgt_speed < 0.05 and src_speed < 0.3:
        return SemanticRelType.SHELTERING_BEHIND

    # Very slow animal → grazing / calm
    if tgt.cls in _ANIMALS and tgt_speed < 0.15 and dist < 5.0:
        return SemanticRelType.GRAZING

    # --- Kinematic fallback ---

    # Occlusion check: tgt is between src and ego (origin)
    src_ego_dist = math.sqrt(src.x**2 + src.y**2)
    tgt_ego_dist = math.sqrt(tgt.x**2 + tgt.y**2)
    if tgt_ego_dist < src_ego_dist * 0.8 and dist < src_ego_dist * 0.7:
        return SemanticRelType.OCCLUDING

    if tgt_speed < 0.05:
        return SemanticRelType.STATIONARY_SAFE
    if closing > 0.8 and lateral < 0.5:
        return SemanticRelType.BLOCKING_PATH
    if lateral > 0.6:
        return SemanticRelType.CROSSING
    if closing < -0.3:
        return SemanticRelType.MOVING_AWAY
    if closing > 0:
        return SemanticRelType.FOLLOWING
    return SemanticRelType.MOVING_AWAY


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
