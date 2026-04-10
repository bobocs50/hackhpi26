"""Interactive Plotly-based SGG Graph Visualization.

Top-down view with:
- Nodes positioned at their (x, y) coordinates
- Ego vehicle node at origin with velocity vector
- Velocity vectors drawn as arrows on all entities
- Semantic relationship edges as colored, rippled lines with labels
- Node color by danger_quality (green→white→red)

Run standalone::

    python -m agri_nav.viz.viz_sgg_graph
"""

from __future__ import annotations

import math

import plotly.graph_objects as go

from agri_nav.dto.config import SGGConfig
from agri_nav.dto.perception import EntityType, KinematicsEntity
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.logic.sgg_processor import (
    EGO_ID,
    SEMANTIC_DANGER_MODIFIERS,
    SceneRelationship,
    SemanticRelType,
    TrackedEntity,
    build_scene_graph,
    collapse_semantic_graph,
    infer_semantic_relations,
    merge_perception,
)

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_SEMANTIC_COLORS: dict[SemanticRelType, str] = {
    SemanticRelType.BLOCKING_PATH: "#e74c3c",      # red
    SemanticRelType.FOLLOWING: "#e67e22",           # orange
    SemanticRelType.CROSSING: "#f39c12",            # amber
    SemanticRelType.MOVING_AWAY: "#2ecc71",         # green
    SemanticRelType.STATIONARY_SAFE: "#3498db",     # blue
    SemanticRelType.OCCLUDING: "#9b59b6",           # purple
}


def _danger_to_rgb(dq: float) -> str:
    """Map danger_quality [0,1] to green→white→red."""
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
# Public API
# ---------------------------------------------------------------------------


def plot_scene_graph(
    entities: list[TrackedEntity],
    semantic_rels: list[SceneRelationship],
    *,
    title: str = "SGG — Scene Graph (interactive)",
    show: bool = True,
) -> go.Figure:
    """Render the SGG as an interactive Plotly scatter with edges and arrows."""

    fig = go.Figure()

    # -- Semantic edges (rippled colored lines with labels) ------------------
    for rel in semantic_rels:
        src = next((e for e in entities if e.id == rel.source_id), None)
        tgt = next((e for e in entities if e.id == rel.target_id), None)
        if src is None or tgt is None:
            continue

        sem = rel.semantic_label
        color = _SEMANTIC_COLORS.get(sem, "#95a5a6") if sem else "#95a5a6"
        modifier = rel.danger_modifier
        mod_str = f"+{modifier:.2f}" if modifier >= 0 else f"{modifier:.2f}"
        label_text = f"{sem.value if sem else 'spatial'} ({mod_str})"

        # Rippled edge: sinusoidal perturbation along the perpendicular
        n_pts = 30
        dx = tgt.x - src.x
        dy = tgt.y - src.y
        length = math.sqrt(dx**2 + dy**2) or 1.0
        # Perpendicular unit
        px, py = -dy / length, dx / length
        amplitude = 0.12
        xs, ys = [], []
        for i in range(n_pts + 1):
            t = i / n_pts
            base_x = src.x + dx * t
            base_y = src.y + dy * t
            ripple = amplitude * math.sin(t * 6 * math.pi)
            xs.append(base_x + px * ripple)
            ys.append(base_y + py * ripple)

        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines",
            line=dict(color=color, width=2.5, dash="solid"),
            hoverinfo="text",
            hovertext=label_text,
            showlegend=False,
        ))

        # Edge label at midpoint
        mid_x = (src.x + tgt.x) / 2 + px * 0.3
        mid_y = (src.y + tgt.y) / 2 + py * 0.3
        fig.add_trace(go.Scatter(
            x=[mid_x], y=[mid_y], mode="text",
            text=[label_text], textfont=dict(size=9, color=color),
            showlegend=False, hoverinfo="skip",
        ))

    # -- Velocity vectors (as annotations) -----------------------------------
    for ent in entities:
        speed = math.sqrt(ent.vx**2 + ent.vy**2)
        if speed < 0.01:
            continue
        arrow_scale = 1.5
        fig.add_annotation(
            x=ent.x + ent.vx * arrow_scale,
            y=ent.y + ent.vy * arrow_scale,
            ax=ent.x, ay=ent.y,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True,
            arrowhead=3, arrowsize=1.5, arrowwidth=2,
            arrowcolor="#2c3e50" if not ent.is_ego else "#2980b9",
        )

    # -- Entity nodes --------------------------------------------------------
    # Separate ego, point, and area entities
    point_ents = [e for e in entities if not e.is_ego and e.entity_type != EntityType.AREA]
    ego_ents = [e for e in entities if e.is_ego]

    # Point entities
    if point_ents:
        ttc_labels = [
            f"TTC={e.ttc:.1f}s" if e.ttc != float("inf") else "TTC=∞"
            for e in point_ents
        ]
        hover_texts = [
            f"<b>{e.cls}</b> (id={e.id})<br>"
            f"q={e.danger_quality:.3f}  c={e.smoothed_certainty:.3f}<br>"
            f"{ttc}<br>"
            f"v=({e.vx:.1f}, {e.vy:.1f}) m/s<br>"
            f"pos=[{e.x:.1f}, {e.y:.1f}, 1]"
            for e, ttc in zip(point_ents, ttc_labels)
        ]
        fig.add_trace(go.Scatter(
            x=[e.x for e in point_ents],
            y=[e.y for e in point_ents],
            mode="markers+text",
            marker=dict(
                size=[18 + 14 * e.smoothed_certainty for e in point_ents],
                color=[_danger_to_rgb(e.danger_quality) for e in point_ents],
                line=dict(width=2, color="#2c3e50"),
            ),
            text=[f"{e.cls}\n(id={e.id})" for e in point_ents],
            textposition="top center",
            textfont=dict(size=10, color="#2c3e50"),
            hovertext=hover_texts,
            hoverinfo="text",
            name="Entities",
        ))

    # Ego node
    if ego_ents:
        ego = ego_ents[0]
        fig.add_trace(go.Scatter(
            x=[ego.x], y=[ego.y],
            mode="markers+text",
            marker=dict(
                size=30, color="#3498db",
                symbol="triangle-up",
                line=dict(width=3, color="#2c3e50"),
            ),
            text=["EGO"],
            textposition="bottom center",
            textfont=dict(size=11, color="#2980b9", family="Arial Black"),
            hovertext=[f"<b>Ego Vehicle</b><br>v=({ego.vx:.1f}, {ego.vy:.1f}) m/s"],
            hoverinfo="text",
            name="Ego Vehicle",
        ))

    # -- Danger colorbar (fake trace for reference) --------------------------
    dq_values = [i / 20 for i in range(21)]
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers",
        marker=dict(
            size=0,
            colorscale=[[0, "#2ecc71"], [0.5, "#ffffff"], [1.0, "#e74c3c"]],
            cmin=0, cmax=1,
            colorbar=dict(title="danger_quality", thickness=15, len=0.5),
            showscale=True, color=[0.5],
        ),
        showlegend=False, hoverinfo="skip",
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
        legend=dict(x=0.01, y=0.99),
        width=900, height=700,
        margin=dict(l=60, r=60, t=60, b=60),
    )

    if show:
        fig.show()
    return fig


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def _demo() -> None:
    """Generate a synthetic scene, infer semantics, and visualize."""
    ego_vy = 3.0

    kins = [
        KinematicsEntity(id=1, cls="human", x=0.5, y=4.0, vx=-0.2, vy=-1.0,
                         detection_confidence=0.95, track_age=25),
        KinematicsEntity(id=2, cls="tractor", x=-3.0, y=8.0, vx=0.0, vy=-0.5,
                         detection_confidence=0.80, track_age=40),
        KinematicsEntity(id=3, cls="bush", x=2.0, y=3.0, vx=0.0, vy=0.0,
                         detection_confidence=0.70, track_age=60),
        KinematicsEntity(id=4, cls="deer", x=-1.0, y=6.0, vx=0.8, vy=-0.3,
                         detection_confidence=0.85, track_age=8),
        KinematicsEntity(id=5, cls="post", x=3.5, y=7.0, vx=0.0, vy=0.0,
                         detection_confidence=0.90, track_age=100),
        KinematicsEntity(id=6, cls="dog", x=1.0, y=5.5, vx=-0.5, vy=-0.8,
                         detection_confidence=0.88, track_age=15),
        KinematicsEntity(id=7, cls="crop", x=4.0, y=5.0, vx=0.0, vy=0.0,
                         detection_confidence=0.60, track_age=100,
                         entity_type=EntityType.AREA, extent_x=2.0, extent_y=3.0),
    ]

    # TTC-based inference
    inf_cfg = SGGInferenceConfig(ego_vy=ego_vy)
    sems = infer_semantics(kins, inf_cfg)

    cfg = SGGConfig()
    tracked = merge_perception(kins, sems, cfg, ego_vy=ego_vy)

    # Build spatial graph (without area entities, with ego)
    nodes, spatial_rels = build_scene_graph(tracked, ego_vy=ego_vy)

    # Infer semantic relationships (ego → entities)
    semantic_rels = infer_semantic_relations(nodes, ego_vy=ego_vy)

    # Collapse: apply semantic modifiers to danger_quality
    collapsed_nodes = collapse_semantic_graph(nodes, semantic_rels)

    print("=== Semantic Relationships ===")
    for r in semantic_rels:
        ent = next((e for e in nodes if e.id == r.target_id), None)
        cls_name = ent.cls if ent else "?"
        mod = r.danger_modifier
        mod_str = f"+{mod:.2f}" if mod >= 0 else f"{mod:.2f}"
        print(f"  ego → {cls_name:>8} (id={r.target_id}):  {r.semantic_label.value:20s}  Δq={mod_str}")

    print("\n=== Collapsed Danger Qualities ===")
    for n in collapsed_nodes:
        if n.is_ego:
            continue
        orig = next((e for e in nodes if e.id == n.id), None)
        dq_orig = orig.danger_quality if orig else 0.0
        print(f"  {n.cls:>8} (id={n.id}): q={dq_orig:.4f} → {n.danger_quality:.4f}")

    plot_scene_graph(collapsed_nodes, semantic_rels)


if __name__ == "__main__":
    _demo()
