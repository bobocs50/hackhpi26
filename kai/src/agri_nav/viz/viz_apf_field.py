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
from agri_nav.dto.perception import (
    CropOccupancyGrid,
    DangerClass,
    KinematicsEntity,
)
from agri_nav.logic import apf_lateral as lat
from agri_nav.logic import apf_longitudinal as lon
from agri_nav.logic.sgg_inference import SGGInferenceConfig, infer_semantics
from agri_nav.logic.sgg_processor import TrackedEntity, merge_perception
from agri_nav.service.apf_service import APFService, VehicleState


# ---------------------------------------------------------------------------
# Potential field computation
# ---------------------------------------------------------------------------


def compute_potential_surface(
    x_range: np.ndarray,
    y_range: np.ndarray,
    entities: list[TrackedEntity],
    cfg: APFConfig,
) -> np.ndarray:
    """Evaluate the combined repulsive potential on a 2D grid."""
    X, Y = np.meshgrid(x_range, y_range)
    Z = np.zeros_like(X)

    for ent in entities:
        if getattr(ent, "is_ego", False):
            continue
        xp, yp = lat.predict_position(ent.x, ent.y, ent.vx, ent.vy, cfg.lookahead_t)
        dx = X - xp
        dy = Y - yp
        dist = np.sqrt(dx**2 + dy**2) + cfg.epsilon
        decay = np.exp(-cfg.alpha_decay * np.maximum(dy, 0.0))

        if ent.danger_class == DangerClass.CROSSABLE:
            scale = 0.2
        elif ent.danger_class == DangerClass.TARGET:
            scale = 0.0
        else:
            scale = 1.0

        Z += scale * (ent.smoothed_certainty * ent.danger_quality / dist) * decay

    return Z


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DANGER_COLORS = {
    DangerClass.MUST_AVOID: "#e74c3c",
    DangerClass.TARGET: "#f39c12",
    DangerClass.CROSSABLE: "#2ecc71",
}


def plot_apf_field(
    entities: list[TrackedEntity],
    crop_grid: CropOccupancyGrid,
    vehicle: VehicleState,
    cfg: APFConfig | None = None,
    *,
    grid_extent: float = 12.0,
    grid_resolution: float = 0.25,
    title: str = "APF — 3D Force Field (interactive)",
    show: bool = True,
) -> go.Figure:
    """Render the APF potential surface and control vector in interactive 3D."""
    if cfg is None:
        cfg = APFConfig()

    # -- Compute force field surface -----------------------------------------
    x_vals = np.arange(-grid_extent, grid_extent, grid_resolution)
    y_vals = np.arange(-2, grid_extent * 1.5, grid_resolution)
    Z_raw = compute_potential_surface(x_vals, y_vals, entities, cfg)
    Z = np.log1p(Z_raw)
    X, Y = np.meshgrid(x_vals, y_vals)

    # -- Run APF controller --------------------------------------------------
    svc = APFService(cfg)
    out = svc.compute(entities, crop_grid, vehicle)

    # -- Build corridor polygon ----------------------------------------------
    corridor = lon.build_safety_corridor(
        vehicle.v_current, cfg.theta_max, cfg.machine_width, cfg.corridor_length_factor
    )
    corridor_xy = np.array(corridor.exterior.coords)

    # -- Plotly figure -------------------------------------------------------
    fig = go.Figure()

    # Surface
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z,
        colorscale="YlOrRd",
        opacity=0.7,
        showscale=True,
        colorbar=dict(title="log₁₊(U)", thickness=15, len=0.5, x=1.02),
        name="Potential Field",
        hovertemplate="x=%{x:.1f}m  y=%{y:.1f}m<br>U=%{z:.3f}<extra></extra>",
    ))

    # Entity markers
    for ent in entities:
        if ent.is_ego:
            continue
        xp, yp = lat.predict_position(ent.x, ent.y, ent.vx, ent.vy, cfg.lookahead_t)
        xi = int((xp + grid_extent) / grid_resolution)
        yi = int((yp + 2) / grid_resolution)
        xi = max(0, min(xi, Z.shape[1] - 1))
        yi = max(0, min(yi, Z.shape[0] - 1))
        z_ent = float(Z[yi, xi]) + 0.1

        color = _DANGER_COLORS.get(ent.danger_class, "#95a5a6")

        fig.add_trace(go.Scatter3d(
            x=[xp], y=[yp], z=[z_ent],
            mode="markers+text",
            marker=dict(size=8, color=color, line=dict(width=1, color="black")),
            text=[f"{ent.cls} (q={ent.danger_quality:.2f})"],
            textposition="top center",
            textfont=dict(size=9),
            hovertext=[
                f"<b>{ent.cls}</b> (id={ent.id})<br>"
                f"q={ent.danger_quality:.3f}  c={ent.smoothed_certainty:.3f}<br>"
                f"TTC={ent.ttc:.1f}s<br>"
                f"class={ent.danger_class.value}"
            ],
            hoverinfo="text",
            showlegend=False,
        ))

    # Vehicle marker
    fig.add_trace(go.Scatter3d(
        x=[vehicle.x], y=[vehicle.y], z=[0],
        mode="markers+text",
        marker=dict(size=12, color="#3498db", symbol="diamond",
                    line=dict(width=2, color="black")),
        text=["EGO"],
        textposition="bottom center",
        textfont=dict(size=11, color="#2980b9"),
        hovertext=[f"<b>Ego Vehicle</b><br>V={vehicle.v_current:.1f} m/s"],
        hoverinfo="text",
        name="Vehicle",
    ))

    # Control vector
    steer_x = math.sin(out.steering.delta_theta) * 2.0
    steer_y = math.cos(out.steering.delta_theta) * out.velocity.v_target
    fig.add_trace(go.Scatter3d(
        x=[vehicle.x, vehicle.x + steer_x],
        y=[vehicle.y, vehicle.y + steer_y],
        z=[0, 0],
        mode="lines",
        line=dict(color="#2980b9", width=6),
        name=f"Δθ={out.steering.delta_theta:.3f} rad, V={out.velocity.v_target:.2f} m/s",
    ))

    # Safety corridor
    cx = [c[0] + vehicle.x for c in corridor_xy]
    cy = [c[1] + vehicle.y for c in corridor_xy]
    cz = [0] * len(corridor_xy)
    fig.add_trace(go.Scatter3d(
        x=cx, y=cy, z=cz,
        mode="lines",
        line=dict(color="#2c3e50", width=3, dash="dash"),
        name="Safety Corridor",
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
                         entity_type="area", extent_x=2.0, extent_y=3.0),
    ]

    vehicle = VehicleState(x=0.0, y=0.0, v_current=3.0, heading=0.0)
    inf_cfg = SGGInferenceConfig(ego_vy=vehicle.v_current)
    sems = infer_semantics(kins, inf_cfg)

    print("=== TTC-based SGG Inference ===")
    for s in sems:
        kin = next(k for k in kins if k.id == s.id)
        print(f"  {kin.cls:>8} (id={s.id}): c={s.certainty:.4f}  q={s.danger_quality:.4f}")

    cfg_sgg = SGGConfig()
    tracked = merge_perception(kins, sems, cfg_sgg, ego_vy=vehicle.v_current)

    grid_data = np.zeros((40, 40))
    grid_data[:, 28:] = 1.0
    crop_grid = CropOccupancyGrid(data=grid_data, resolution=0.5, origin_x=-5.0, origin_y=-2.0)

    apf_cfg = APFConfig()

    svc = APFService(apf_cfg)
    out = svc.compute(tracked, crop_grid, vehicle)
    print(f"\nSteering: Δθ = {out.steering.delta_theta:.4f} rad")
    print(f"Velocity: V  = {out.velocity.v_target:.4f} m/s")

    plot_apf_field(tracked, crop_grid, vehicle, apf_cfg)


if __name__ == "__main__":
    _demo()
