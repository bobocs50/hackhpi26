"""Interactive Plotly visualization of the initial Mock SGG entity graph.

Renders a **reified** scene graph where every semantic relationship is
drawn as its own node (diamond) positioned between the two entities it
connects.  This makes the flow ``Entity ──▶ [relation] ──▶ Entity``
explicit and shows the ``danger_score_contribution`` of each relation.

Two edge layers are present:

1. **Ego → entity** relations (dashed outgoing links from ego).
2. **Entity → entity** relations (solid links from mock SGG).

Each relation node is color-coded by semantic type and displays its
danger contribution score on hover/click.

Run standalone::

    python -m agri_nav.viz.viz_mock_sgg
"""

from __future__ import annotations

import math

import plotly.graph_objects as go

from agri_nav.dto.visualization import (
    MockSGGEdgeViz,
    MockSGGRelationNodeViz,
    MockSGGVisualData,
)
from agri_nav.logic.sgg_processor import SemanticRelType


# ---------------------------------------------------------------------------
# Color palette per semantic relationship type
# ---------------------------------------------------------------------------

_SEMANTIC_COLORS: dict[str, str] = {
    # Motion-based
    SemanticRelType.BLOCKING_PATH.value: "#e74c3c",
    SemanticRelType.FOLLOWING.value: "#e67e22",
    SemanticRelType.CROSSING.value: "#f39c12",
    SemanticRelType.MOVING_AWAY.value: "#2ecc71",
    SemanticRelType.STATIONARY_SAFE.value: "#3498db",
    SemanticRelType.OCCLUDING.value: "#9b59b6",
    # Agricultural context
    SemanticRelType.HOLDING_LEASH.value: "#c0392b",
    SemanticRelType.FLEEING_FROM.value: "#d35400",
    SemanticRelType.TERRAIN_HAZARD.value: "#8b4513",
    SemanticRelType.SHELTERING_BEHIND.value: "#7f8c8d",
    SemanticRelType.GRAZING.value: "#27ae60",
}

_DEFAULT_EDGE_COLOR = "#95a5a6"


def _danger_to_rgb(dq: float) -> str:
    """Map danger_quality [0,1] to green → white → red."""
    if dq <= 0.5:
        t = dq / 0.5
        r = int(46 + (255 - 46) * t)
        g = int(204 + (255 - 204) * t)
        b = int(113 + (255 - 113) * t)
    else:
        t = (dq - 0.5) / 0.5
        r = int(255 - (255 - 231) * t)
        g = int(255 - (255 - 76) * t)
        b = int(255 - (255 - 60) * t)
    return f"rgb({r},{g},{b})"


# ---------------------------------------------------------------------------
# Edge drawing helper
# ---------------------------------------------------------------------------


def _draw_edge(
    fig: go.Figure,
    edge: MockSGGEdgeViz,
    *,
    dash: str = "solid",
    width: int = 2,
    opacity: float = 0.7,
) -> None:
    """Draw a straight directed edge with an arrowhead annotation."""
    fig.add_trace(go.Scatter(
        x=[edge.source_x, edge.target_x],
        y=[edge.source_y, edge.target_y],
        mode="lines",
        line=dict(color=edge.color, width=width, dash=dash),
        opacity=opacity,
        hoverinfo="skip",
        showlegend=False,
    ))

    # Arrowhead at ~80% from source to target
    t = 0.80
    ax = edge.source_x + (edge.target_x - edge.source_x) * (t - 0.05)
    ay = edge.source_y + (edge.target_y - edge.source_y) * (t - 0.05)
    px = edge.source_x + (edge.target_x - edge.source_x) * t
    py = edge.source_y + (edge.target_y - edge.source_y) * t
    fig.add_annotation(
        x=px, y=py, ax=ax, ay=ay,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True,
        arrowhead=3, arrowsize=1.5, arrowwidth=1.5,
        arrowcolor=edge.color,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_mock_sgg(
    viz_data: MockSGGVisualData,
    *,
    title: str | None = None,
    show: bool = True,
) -> go.Figure:
    """Render the reified mock SGG as an interactive 2-D graph.

    Entities are circles, relations are diamonds positioned between
    their source and target. Edges go source → [relation] → target.
    """
    fig = go.Figure()
    title = title or viz_data.title

    # -- 1. Edges (entity → relation → entity) ------------------------------
    for edge in viz_data.edges:
        is_ego_link = edge.source_id.startswith("ego") or edge.target_id.startswith("ego")
        _draw_edge(
            fig, edge,
            dash="dash" if is_ego_link else "solid",
            width=1.5 if is_ego_link else 2,
            opacity=0.5 if is_ego_link else 0.7,
        )

    # -- 2. Velocity vectors -------------------------------------------------
    for n in viz_data.nodes:
        speed = math.sqrt(n.vx**2 + n.vy**2)
        if speed < 0.01:
            continue
        scale = 1.5
        fig.add_annotation(
            x=n.x + n.vx * scale,
            y=n.y + n.vy * scale,
            ax=n.x, ay=n.y,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True,
            arrowhead=3, arrowsize=1.5, arrowwidth=2,
            arrowcolor="#2980b9" if n.is_ego else "#7f8c8d",
        )

    # -- 3. Entity nodes (non-ego) ------------------------------------------
    non_ego = [n for n in viz_data.nodes if not n.is_ego]
    if non_ego:
        fig.add_trace(go.Scatter(
            x=[n.x for n in non_ego],
            y=[n.y for n in non_ego],
            mode="markers+text",
            marker=dict(
                size=[18 + 14 * n.certainty for n in non_ego],
                color=[_danger_to_rgb(n.danger_quality) for n in non_ego],
                line=dict(width=2, color="#2c3e50"),
            ),
            text=[f"{n.cls}\n(id={n.id})" for n in non_ego],
            textposition="top center",
            textfont=dict(size=10, color="#2c3e50"),
            hovertext=[
                f"<b>{n.cls}</b> (id={n.id})<br>"
                f"q={n.danger_quality:.3f}  c={n.certainty:.3f}<br>"
                f"TTC={n.ttc_label}<br>"
                f"speed={n.speed:.2f} m/s"
                for n in non_ego
            ],
            hoverinfo="text",
            name="Entities",
        ))

    # -- 4. Ego node ---------------------------------------------------------
    ego_nodes = [n for n in viz_data.nodes if n.is_ego]
    if ego_nodes:
        ego = ego_nodes[0]
        fig.add_trace(go.Scatter(
            x=[ego.x], y=[ego.y],
            mode="markers+text",
            marker=dict(
                size=30, color="#3498db", symbol="triangle-up",
                line=dict(width=3, color="#2c3e50"),
            ),
            text=["EGO"],
            textposition="bottom center",
            textfont=dict(size=11, color="#2980b9", family="Arial Black"),
            hovertext=[f"<b>EGO</b><br>v=({ego.vx:.1f}, {ego.vy:.1f}) m/s"],
            hoverinfo="text",
            name="Ego Vehicle",
        ))

    # -- 5. Relation nodes (diamonds) ----------------------------------------
    rel_nodes = viz_data.relation_nodes
    if rel_nodes:
        # Alternate text positions to reduce overlap
        _positions = ["top center", "bottom center", "middle right", "middle left"]
        fig.add_trace(go.Scatter(
            x=[r.x for r in rel_nodes],
            y=[r.y for r in rel_nodes],
            mode="markers+text",
            marker=dict(
                size=20,
                color=[r.color for r in rel_nodes],
                symbol="diamond",
                line=dict(width=1.5, color="#2c3e50"),
                opacity=0.9,
            ),
            text=[f"{r.danger_contribution:+.2f}" for r in rel_nodes],
            textposition=[_positions[i % len(_positions)] for i in range(len(rel_nodes))],
            textfont=dict(size=8, color="#2c3e50"),
            hovertext=[
                f"<b>{r.label}</b><br>"
                f"danger contribution: {r.danger_contribution:+.2f}<br>"
                f"<i>{r.reasoning}</i>"
                for r in rel_nodes
            ],
            hoverinfo="text",
            name="Relations",
        ))

    # -- 6. Legend entries for semantic types ---------------------------------
    for sem_val, color in _SEMANTIC_COLORS.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(color=color, size=10, symbol="diamond"),
            name=sem_val,
        ))

    # -- Layout --------------------------------------------------------------
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis=dict(
            title="x [m] (lateral — left<0, right>0)",
            scaleanchor="y", scaleratio=1,
            zeroline=True, zerolinecolor="#bdc3c7", gridcolor="#ecf0f1",
        ),
        yaxis=dict(
            title="y [m] (forward)",
            zeroline=True, zerolinecolor="#bdc3c7", gridcolor="#ecf0f1",
        ),
        plot_bgcolor="white",
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
        width=1000, height=800,
        margin=dict(l=60, r=60, t=60, b=60),
    )

    if show:
        fig.show()
    return fig


# ---------------------------------------------------------------------------
# VisualData builder  (decouples processor DTOs from viz DTOs)
# ---------------------------------------------------------------------------


def build_mock_sgg_viz(
    nodes: list,
    ego_rels: list,
    entity_rels: list,
    ego_vx: float = 0.0,
    ego_vy: float = 0.0,
) -> MockSGGVisualData:
    """Assemble a :class:`MockSGGVisualData` with reified relation nodes.

    Each relationship ``(src, label, tgt)`` becomes:

    * A **relation node** (diamond) at the midpoint of src ↔ tgt,
      offset perpendicular to avoid overlap.
    * Two **edges**: ``src → relation`` and ``relation → tgt``.
    """
    from agri_nav.dto.visualization import MockSGGNodeViz

    node_by_id = {n.id: n for n in nodes}

    viz_nodes: list[MockSGGNodeViz] = []
    for n in nodes:
        speed = math.sqrt(n.vx**2 + n.vy**2)
        ttc_str = "" if n.is_ego else ("∞" if n.ttc == float("inf") else f"{n.ttc:.1f}s")
        viz_nodes.append(MockSGGNodeViz(
            id=n.id, cls=n.cls, is_ego=n.is_ego,
            x=n.x, y=n.y, vx=n.vx, vy=n.vy,
            speed=round(speed, 3),
            danger_quality=n.danger_quality,
            certainty=n.smoothed_certainty,
            ttc_label=ttc_str,
        ))

    rel_viz_nodes: list[MockSGGRelationNodeViz] = []
    edges: list[MockSGGEdgeViz] = []

    # Track how many relations share the same (src, tgt) pair for offset
    pair_counts: dict[tuple[int, int], int] = {}

    all_rels = list(ego_rels) + list(entity_rels)
    for rel in all_rels:
        src = node_by_id.get(rel.source_id)
        tgt = node_by_id.get(rel.target_id)
        if src is None or tgt is None:
            continue

        sem_val = rel.semantic_label.value if rel.semantic_label else "unknown"
        color = _SEMANTIC_COLORS.get(sem_val, _DEFAULT_EDGE_COLOR)

        # Perpendicular offset so overlapping relations don't stack
        pair_key = (min(rel.source_id, rel.target_id), max(rel.source_id, rel.target_id))
        idx = pair_counts.get(pair_key, 0)
        pair_counts[pair_key] = idx + 1

        dx = tgt.x - src.x
        dy = tgt.y - src.y
        length = math.sqrt(dx**2 + dy**2) or 1.0
        perp_x, perp_y = -dy / length, dx / length
        offset = 0.6 * (idx - 0.5)  # spread relations apart

        mx = (src.x + tgt.x) / 2 + perp_x * offset
        my = (src.y + tgt.y) / 2 + perp_y * offset

        rel_id = f"rel_{rel.source_id}_{rel.target_id}_{sem_val}"

        rel_viz_nodes.append(MockSGGRelationNodeViz(
            id=rel_id,
            semantic_type=sem_val,
            danger_contribution=rel.danger_modifier,
            reasoning=rel.reasoning,
            label=sem_val,
            source_entity_id=rel.source_id,
            target_entity_id=rel.target_id,
            x=mx,
            y=my,
            color=color,
        ))

        # Edge: source entity → relation node
        edges.append(MockSGGEdgeViz(
            source_id=str(rel.source_id),
            target_id=rel_id,
            source_x=src.x, source_y=src.y,
            target_x=mx, target_y=my,
            color=color,
        ))

        # Edge: relation node → target entity
        edges.append(MockSGGEdgeViz(
            source_id=rel_id,
            target_id=str(rel.target_id),
            source_x=mx, source_y=my,
            target_x=tgt.x, target_y=tgt.y,
            color=color,
        ))

    return MockSGGVisualData(
        nodes=viz_nodes,
        relation_nodes=rel_viz_nodes,
        edges=edges,
    )


# ---------------------------------------------------------------------------
# Demo / standalone entry point
# ---------------------------------------------------------------------------


def _demo() -> None:
    """Full pipeline: detect → infer → mock SGG → visualize initial graph."""
    from agri_nav.demo_scene import DEMO_KINEMATICS_POINT_ONLY, EGO_VY
    from agri_nav.dto.config import SGGConfig
    from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
    from agri_nav.logic.sgg_processor import (
        build_scene_graph,
        infer_semantic_relations,
        merge_perception,
        mock_sgg_entity_graph,
    )

    kins = DEMO_KINEMATICS_POINT_ONLY

    # 1. TTC-based inference
    inf_cfg = SGGInferenceConfig(ego_vy=EGO_VY)
    sems = infer_semantics(kins, inf_cfg)

    # 2. Merge into tracked entities
    cfg = SGGConfig()
    tracked = merge_perception(kins, sems, cfg, ego_vy=EGO_VY)

    # 3. Build spatial graph (inserts ego node)
    nodes, _ = build_scene_graph(tracked, ego_vy=EGO_VY)

    # 4. Ego → entity semantic relations
    ego_rels = infer_semantic_relations(nodes, ego_vy=EGO_VY)

    # 5. Entity → entity semantic relations (the mock SGG step)
    entity_rels = mock_sgg_entity_graph(nodes, ego_vy=EGO_VY)

    # 6. Print summary
    print("=== Mock SGG — Reified Entity Graph ===")
    print(f"  Entity nodes:    {len(nodes)}")
    print(f"  Ego→entity rels: {len(ego_rels)}")
    print(f"  Entity↔entity rels: {len(entity_rels)}")
    print()
    for r in ego_rels:
        tgt = next((n for n in nodes if n.id == r.target_id), None)
        name = tgt.cls if tgt else "?"
        print(f"  ego ──▶ [{r.semantic_label.value:20s} {r.danger_modifier:+.2f}] ──▶ {name}")
    print()
    for r in entity_rels:
        src = next((n for n in nodes if n.id == r.source_id), None)
        tgt = next((n for n in nodes if n.id == r.target_id), None)
        s_name = src.cls if src else "?"
        t_name = tgt.cls if tgt else "?"
        print(f"  {s_name:>8} ──▶ [{r.semantic_label.value:20s} {r.danger_modifier:+.2f}] ──▶ {t_name}")
        print(f"           reasoning: {r.reasoning}")

    # 7. Build viz data and render
    viz = build_mock_sgg_viz(nodes, ego_rels, entity_rels, ego_vy=EGO_VY)
    print(f"\n  Total relation nodes: {len(viz.relation_nodes)}")
    print(f"  Total edges:         {len(viz.edges)}")
    plot_mock_sgg(viz)


if __name__ == "__main__":
    _demo()
