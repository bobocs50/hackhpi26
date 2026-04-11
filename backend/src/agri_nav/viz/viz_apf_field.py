"""Interactive Plotly-based 3D APF Force Field Visualization.

Renders:
1. A 3D surface showing the log-scaled repulsive potential field.
2. Entity positions as colored scatter markers.
3. The resulting steering/velocity vector.
4. The safety corridor polygon.

Run standalone::

    python -m agri_nav.viz.viz_apf_field
"""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go

from agri_nav.dto.config import APFConfig, SGGConfig
from agri_nav.dto.perception import CropOccupancyGrid, KinematicsEntity
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.logic.sgg_processor import TrackedEntity, merge_perception
from agri_nav.service.apf_service import APFService, VehicleState
from agri_nav.dto.visualization import APFVisualData

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot_apf_field(
    viz_data: APFVisualData,
    *,
    title: str = "APF — 3D Force Field (interactive)",
    show: bool = True,
) -> go.Figure:
    """Render the APF potential surface and control vector in interactive 3D."""

    fig = go.Figure()

    # -- Surface -------------------------------------------------------------
    X, Y = np.meshgrid(viz_data.x_grid, viz_data.y_grid)
    Z = np.array(viz_data.z_surface)

    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z,
        colorscale="YlOrRd",
        opacity=0.7,
        showscale=True,
        colorbar=dict(title="log₁₊(U)", thickness=15, len=0.5, x=1.02),
        name="Potential Field",
        hovertemplate="x=%{x:.1f}m  y=%{y:.1f}m<br>U=%{z:.3f}<extra></extra>",
    ))

    # -- Entity markers ------------------------------------------------------
    for ent in viz_data.entities:
        # Interpolate Z surface height for marker text placement
        xi = int((ent.x + viz_data.extent_x) / (viz_data.x_grid[1] - viz_data.x_grid[0] + 1e-9))
        yi = int((ent.y + 2) / (viz_data.y_grid[1] - viz_data.y_grid[0] + 1e-9))
        xi = max(0, min(xi, Z.shape[1] - 1))
        yi = max(0, min(yi, Z.shape[0] - 1))
        z_ent = float(Z[yi, xi]) + 0.1

        fig.add_trace(go.Scatter3d(
            x=[ent.x], y=[ent.y], z=[z_ent],
            mode="markers+text",
            marker=dict(size=8, color=ent.color, line=dict(width=1, color="black")),
            text=[f"{ent.cls} (q={ent.danger_quality:.2f})"],
            textposition="top center",
            textfont=dict(size=9),
            hovertext=[
                f"<b>{ent.cls}</b> (id={ent.id})<br>"
                f"q={ent.danger_quality:.3f}  c={ent.smoothed_certainty:.3f}<br>"
                f"TTC={ent.ttc_label}<br>"
                f"class={ent.danger_class}"
            ],
            hoverinfo="text",
            showlegend=False,
        ))

    # -- Ego vehicle marker --------------------------------------------------
    fig.add_trace(go.Scatter3d(
        x=[viz_data.ego_x], y=[viz_data.ego_y], z=[0],
        mode="markers+text",
        marker=dict(size=12, color="#3498db", symbol="diamond",
                    line=dict(width=2, color="black")),
        text=["EGO"],
        textposition="bottom center",
        textfont=dict(size=11, color="#2980b9"),
        hovertext=[f"<b>Ego Vehicle</b><br>V={viz_data.ego_v:.1f} m/s"],
        hoverinfo="text",
        name="Vehicle",
    ))

    # -- Control vector ------------------------------------------------------
    fig.add_trace(go.Scatter3d(
        x=[viz_data.ego_x, viz_data.ego_x + viz_data.control_steer_x],
        y=[viz_data.ego_y, viz_data.ego_y + viz_data.control_steer_y],
        z=[0, 0],
        mode="lines",
        line=dict(color="#2980b9", width=6),
        name=f"Δθ={viz_data.delta_theta:.3f} rad, V={viz_data.v_target:.2f} m/s",
    ))

    # -- Safety corridor -----------------------------------------------------
    cx = [pt[0] for pt in viz_data.corridor_xy]
    cy = [pt[1] for pt in viz_data.corridor_xy]
    cz = [0] * len(viz_data.corridor_xy)
    fig.add_trace(go.Scatter3d(
        x=cx, y=cy, z=cz,
        mode="lines",
        line=dict(color="#2c3e50", width=3, dash="dash"),
        name="Safety Corridor",
    ))

    # -- Predicted Trajectory Rollout ----------------------------------------
    if viz_data.trajectory:
        tx, ty, tz = [], [], []
        for pt in viz_data.trajectory:
            x_pt, y_pt = pt[0], pt[1]
            xi = int((x_pt + viz_data.extent_x) / (viz_data.x_grid[1] - viz_data.x_grid[0] + 1e-9))
            yi = int((y_pt + 2) / (viz_data.y_grid[1] - viz_data.y_grid[0] + 1e-9))
            xi = max(0, min(xi, Z.shape[1] - 1))
            yi = max(0, min(yi, Z.shape[0] - 1))
            z_surf = float(Z[yi, xi]) + 0.05
            tx.append(x_pt)
            ty.append(y_pt)
            tz.append(z_surf)

        fig.add_trace(go.Scatter3d(
            x=tx, y=ty, z=tz,
            mode="lines+markers",
            line=dict(color="#8e44ad", width=6, dash="solid"),
            marker=dict(size=4, color="#8e44ad"),
            name="Gradient Descent Path",
        ))

    # -- Layout --------------------------------------------------------------
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        scene=dict(
            xaxis=dict(title="x [m] (lateral)"),
            yaxis=dict(title="y [m] (forward)"),
            zaxis=dict(title="log₁₊(U)"),
            camera=dict(eye=dict(x=-1.5, y=-1.5, z=1.2)),
        ),
        width=1000, height=750,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    if show:
        fig.show()
    return fig


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def _demo() -> None:
    """Generate a synthetic scene, infer semantics via TTC, and visualize."""
    from agri_nav.demo_scene import DEMO_KINEMATICS, EGO_VY, make_crop_grid

    kins = DEMO_KINEMATICS
    vehicle = VehicleState(x=0.0, y=0.0, v_current=EGO_VY, heading=0.0)
    inf_cfg = SGGInferenceConfig(ego_vy=vehicle.v_current)
    sems = infer_semantics(kins, inf_cfg)

    print("=== TTC-based SGG Inference ===")
    for s in sems:
        kin = next(k for k in kins if k.id == s.id)
        print(f"  {kin.cls:>8} (id={s.id}): c={s.certainty:.4f}  q={s.danger_quality:.4f}")

    cfg_sgg = SGGConfig()
    tracked = merge_perception(kins, sems, cfg_sgg, ego_vy=vehicle.v_current)

    crop_grid = make_crop_grid()

    apf_cfg = APFConfig()

    svc = APFService(apf_cfg)
    out = svc.compute(tracked, crop_grid, vehicle, render_viz=True)
    
    print(f"\nSteering: Δθ = {out.steering.delta_theta:.4f} rad")
    print(f"Velocity: V  = {out.velocity.v_target:.4f} m/s")

    if out.visual_data:
        plot_apf_field(out.visual_data)

if __name__ == "__main__":
    _demo()
