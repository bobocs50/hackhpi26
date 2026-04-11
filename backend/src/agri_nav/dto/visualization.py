"""Pydantic DTOs for frontend visualization payloads.

These models encapsulate the raw structured data needed to render the
SGG and APF visualizations in a web frontend (e.g. using plotly.js),
decoupling the core backend services from Plotly Python Figure objects.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# SGG Visualization DTOs
# ---------------------------------------------------------------------------


class SGGNodeViz(BaseModel):
    """Visual representation of a single node in the scene graph."""

    id: int
    cls: str
    is_ego: bool
    x: float
    y: float
    vx: float
    vy: float
    danger_quality: float
    smoothed_certainty: float
    ttc_label: str  # e.g., "1.5s" or "∞"


class SGGEdgeViz(BaseModel):
    """Visual representation of a semantic edge."""

    source_x: float
    source_y: float
    target_x: float
    target_y: float
    label: str  # e.g., "blocking_path (+0.30)"
    color: str  # `#hex` color for the edge
    reasoning: str = ""  # AI reasoning for the danger score


class SGGDistanceLineViz(BaseModel):
    """Visual line showing physical distance from Ego to an entity."""

    target_x: float
    target_y: float
    distance: float


class SGGVisualData(BaseModel):
    """Complete SGG graph payload for the frontend."""

    model_config = ConfigDict(frozen=True)

    nodes: list[SGGNodeViz] = Field(default_factory=list)
    edges: list[SGGEdgeViz] = Field(default_factory=list)
    distance_lines: list[SGGDistanceLineViz] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mock SGG (Initial Entity Graph) Visualization DTOs
# ---------------------------------------------------------------------------


class MockSGGNodeViz(BaseModel):
    """A node in the initial mock SGG — before any danger collapse."""

    id: int
    cls: str
    is_ego: bool
    x: float
    y: float
    vx: float
    vy: float
    speed: float
    danger_quality: float
    certainty: float
    ttc_label: str


class MockSGGEdgeViz(BaseModel):
    """A simple directed link between two node ids (entity or relation)."""

    source_id: str = Field(description="Node key of the source (entity id or relation node id)")
    target_id: str = Field(description="Node key of the target")
    source_x: float
    source_y: float
    target_x: float
    target_y: float
    color: str


class MockSGGRelationNodeViz(BaseModel):
    """A reified relation node: the predicate becomes a visible graph node.

    Example: Human ──▶ [blocking_path +0.30] ──▶ Dog
    """

    id: str = Field(description="Unique key, e.g. 'rel_1_6_blocking_path'")
    semantic_type: str
    danger_contribution: float = Field(description="Score added to target's danger_quality")
    reasoning: str
    label: str = Field(description="Short display label, e.g. 'blocking_path'")
    source_entity_id: int
    target_entity_id: int
    x: float
    y: float
    color: str


class MockSGGVisualData(BaseModel):
    """Complete payload for the initial (pre-collapse) mock SGG visualization.

    Relations are first-class nodes: each relationship is a diamond-shaped
    node positioned between its source and target entities, with two
    directed edges (source → relation → target).
    """

    model_config = ConfigDict(frozen=True)

    title: str = "Mock SGG — Initial Entity Relationship Graph"
    nodes: list[MockSGGNodeViz] = Field(default_factory=list)
    relation_nodes: list[MockSGGRelationNodeViz] = Field(
        default_factory=list,
        description="Reified relation nodes (predicates as graph nodes)",
    )
    edges: list[MockSGGEdgeViz] = Field(
        default_factory=list,
        description="Directed links: entity→relation and relation→entity",
    )


# ---------------------------------------------------------------------------
# APF Visualization DTOs
# ---------------------------------------------------------------------------


class APFEntityViz(BaseModel):
    """Visual marker for an obstacle in the APF field."""

    id: int
    cls: str
    x: float
    y: float
    z: float
    color: str
    danger_quality: float
    smoothed_certainty: float
    ttc_label: str
    danger_class: str


class APFVisualData(BaseModel):
    """Complete 3D APF field payload for the frontend.

    Because the raw 3D mesh (Z) can be large, this structure provides
    down-sampled or specific mesh coordinates to reconstruct the surface.
    """

    model_config = ConfigDict(frozen=True)

    # Surface mesh
    x_grid: list[float]
    y_grid: list[float]
    z_surface: list[list[float]]  # 2D array of log1p(U) evaluate on the grid

    # Ego vehicle
    ego_x: float
    ego_y: float
    ego_v: float

    # Targets and objects
    entities: list[APFEntityViz] = Field(default_factory=list)

    # Bounding arrays limits (for axes)
    extent_x: float
    extent_y: float

    # Control vector line (current control vector)
    control_steer_x: float
    control_steer_y: float
    delta_theta: float
    v_target: float

    # Predicted Rollout Trajectory [(x, y, z), ...]
    trajectory: list[tuple[float, float, float]] = Field(default_factory=list)

    # Safety corridor boundary points [(x, y), ...]
    corridor_xy: list[tuple[float, float]] = Field(default_factory=list)
