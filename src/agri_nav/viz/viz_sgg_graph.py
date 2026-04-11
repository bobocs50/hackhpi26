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
from agri_nav.dto.visualization import SGGVisualData


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
    viz_data: SGGVisualData,
    *,
    title: str = "SGG — Scene Graph (interactive)",
    show: bool = True,
) -> go.Figure:
    """Render the SGG as an interactive Plotly scatter with edges and arrows."""

    fig = go.Figure()

    # -- Semantic edges (rippled colored lines with labels) ------------------
    for rel in viz_data.edges:
        # Rippled edge: sinusoidal perturbation along the perpendicular
        n_pts = 30
        dx = rel.target_x - rel.source_x
        dy = rel.target_y - rel.source_y
        length = math.sqrt(dx**2 + dy**2) or 1.0
        # Perpendicular unit
        px, py = -dy / length, dx / length

        ex = []
        ey = []
        for i in range(n_pts + 1):
            t = i / n_pts
            base_x = rel.source_x + t * dx
            base_y = rel.source_y + t * dy
            # amplitude envelope (zero at ends, max in middle)
            env = math.sin(t * math.pi)
            # wiggle
            wiggle = math.sin(t * math.pi * 6) * 0.15 * env
            ex.append(base_x + px * wiggle)
            ey.append(base_y + py * wiggle)

        fig.add_trace(go.Scatter(
            x=ex, y=ey,
            mode="lines",
            line=dict(color=rel.color, width=2, dash="dot"),
            name=rel.label,
            text=[rel.label] * len(ex),
            hoverinfo="name",
            showlegend=False,
        ))

        # Add label at midpoint
        fig.add_annotation(
            x=rel.source_x + dx * 0.5,
            y=rel.source_y + dy * 0.5,
            text=rel.label,
            showarrow=False,
            font=dict(size=9, color=rel.color),
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor=rel.color,
            borderwidth=1,
            borderpad=2,
        )

    # -- Distance Lines (straight dashed gray with middle label) -------------
    for dist_line in viz_data.distance_lines:
        fig.add_trace(go.Scatter(
            x=[0.0, dist_line.target_x],
            y=[0.0, dist_line.target_y],
            mode="lines",
            line=dict(color="#bdc3c7", width=1, dash="dash"),
            hoverinfo="skip",
            showlegend=False,
        ))
        
        # Add a subtle label offset to 80% to avoid semantic edge label collisions at midpoints
        fig.add_annotation(
            x=dist_line.target_x * 0.8,
            y=dist_line.target_y * 0.8,
            text=f"{dist_line.distance:.1f}m",
            showarrow=False,
            font=dict(size=8, color="#7f8c8d"),
            bgcolor="rgba(255,255,255,0.6)",
        )

    # -- Velocity vectors (as annotations) -----------------------------------
    for n in viz_data.nodes:
        speed = math.sqrt(n.vx**2 + n.vy**2)
        if speed < 0.01:
            continue
        arrow_scale = 1.5
        fig.add_annotation(
            x=n.x + n.vx * arrow_scale,
            y=n.y + n.vy * arrow_scale,
            ax=n.x, ay=n.y,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True,
            arrowhead=3, arrowsize=1.5, arrowwidth=2,
            arrowcolor="#2980b9" if n.is_ego else "#2c3e50",
        )

    # -- Entity nodes --------------------------------------------------------
    # Point entities
    point_nodes = [n for n in viz_data.nodes if not n.is_ego]
    if point_nodes:
        fig.add_trace(go.Scatter(
            x=[n.x for n in point_nodes],
            y=[n.y for n in point_nodes],
            mode="markers+text",
            marker=dict(
                size=[18 + 14 * n.smoothed_certainty for n in point_nodes],
                color=[_danger_to_rgb(n.danger_quality) for n in point_nodes],
                line=dict(width=2, color="#2c3e50"),
            ),
            text=[f"{n.cls}\n(id={n.id})" for n in point_nodes],
            textposition="top center",
            textfont=dict(size=10, color="#2c3e50"),
            hovertext=[
                f"<b>{n.cls}</b> (id={n.id})<br>"
                f"q={n.danger_quality:.3f}  c={n.smoothed_certainty:.3f}<br>"
                f"TTC={n.ttc_label}<br>"
                f"v=({n.vx:.1f}, {n.vy:.1f}) m/s"
                for n in point_nodes
            ],
            hoverinfo="text",
            name="Entities",
        ))

    # Ego node
    ego_nodes = [n for n in viz_data.nodes if n.is_ego]
    if ego_nodes:
        ego = ego_nodes[0]
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
            hovertext=[f"<b>EGO</b><br>v=({ego.vx:.1f}, {ego.vy:.1f}) m/s"],
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

    inf_cfg = SGGInferenceConfig(ego_vy=ego_vy)
    sems = infer_semantics(kins, inf_cfg)

    from agri_nav.logic.sgg_processor import RelationshipType, SEMANTIC_DANGER_MODIFIERS
    entity_rels = [
        # Human following the Dog
        SceneRelationship(
            source_id=1, target_id=6, 
            relation=RelationshipType.NEAR, distance=1.5,
            semantic_label=SemanticRelType.FOLLOWING, 
            danger_modifier=SEMANTIC_DANGER_MODIFIERS[SemanticRelType.FOLLOWING]
        ),
        # Dog moving away from Human
        SceneRelationship(
            source_id=6, target_id=1, 
            relation=RelationshipType.NEAR, distance=1.5,
            semantic_label=SemanticRelType.MOVING_AWAY, 
            danger_modifier=SEMANTIC_DANGER_MODIFIERS[SemanticRelType.MOVING_AWAY]
        ),
        # Tractor crossing near Bush
        SceneRelationship(
            source_id=2, target_id=3, 
            relation=RelationshipType.NEAR, distance=7.0,
            semantic_label=SemanticRelType.CROSSING, 
            danger_modifier=SEMANTIC_DANGER_MODIFIERS[SemanticRelType.CROSSING]
        ),
    ]

    from agri_nav.service.sgg_service import SGGService
    svc = SGGService(SGGConfig())
    out = svc.process(
        kinematics=kins, semantics=sems, 
        entity_sgg_rels=entity_rels, 
        ego_vy=ego_vy, render_viz=True
    )

    print("=== SGG Scene Graph Output ===")
    for n in out.nodes:
        if n.is_ego:
            continue
        print(f"  {n.cls:>8} (id={n.id}): c={n.smoothed_certainty:.4f}  q={n.danger_quality:.4f}")

    if out.visual_data:
        plot_scene_graph(out.visual_data)


if __name__ == "__main__":
    _demo()
