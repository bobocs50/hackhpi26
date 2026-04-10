"""APF service — stateful orchestrator for dual-system vector APF control."""

from __future__ import annotations

import math

import numpy as np

from agri_nav.dto.config import APFConfig
from agri_nav.dto.control import ControlOutput, SteeringCommand, VelocityCommand
from agri_nav.dto.perception import CropOccupancyGrid
from agri_nav.logic import apf_lateral as lat
from agri_nav.logic import apf_longitudinal as lon
from agri_nav.logic.sgg_processor import TrackedEntity


class VehicleState:
    """Minimal vehicle state required by the APF controller."""

    __slots__ = ("x", "y", "v_current", "heading")

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        v_current: float = 0.0,
        heading: float = 0.0,
    ) -> None:
        self.x = x
        self.y = y
        self.v_current = v_current
        self.heading = heading


class APFService:
    """Orchestrates lateral + longitudinal APF for a single control tick.

    Holds mutable state:
    * ``_prev_theta`` — previous steering command (for rate limiting).
    * ``_prev_error`` — previous cross-track error (for PD derivative).

    Usage::

        svc = APFService(config)
        out = svc.compute(entities, crop_grid, vehicle)
        # out.steering.delta_theta, out.velocity.v_target
    """

    def __init__(self, config: APFConfig | None = None) -> None:
        self._cfg = config or APFConfig()
        self._prev_theta: float = 0.0
        self._prev_error: float = 0.0

    # -- public API ----------------------------------------------------------

    def compute(
        self,
        entities: list[TrackedEntity],
        crop_grid: CropOccupancyGrid,
        vehicle: VehicleState,
        render_viz: bool = False,
    ) -> ControlOutput:
        """Run one full APF control tick.

        Returns a ``ControlOutput`` with steering and velocity commands.
        If ``render_viz=True``, embeds the Plotly 3D visualization JSON.
        """
        cfg = self._cfg

        # ── A. Lateral (Steering) ──────────────────────────────────────

        # 1. Crop contour tracking
        gradient = lat.compute_crop_gradient(crop_grid.data, crop_grid.resolution)

        veh_col = int(
            (vehicle.x - crop_grid.origin_x) / crop_grid.resolution
        )
        veh_row = int(
            (vehicle.y - crop_grid.origin_y) / crop_grid.resolution
        )
        # Clamp to grid bounds
        veh_col = max(0, min(veh_col, gradient.shape[1] - 1))
        veh_row = max(0, min(veh_row, gradient.shape[0] - 1))

        offset = lat.find_edge_offset(gradient, veh_col, veh_row, crop_grid.resolution)
        a_edge, error = lat.compute_attractive_vector(
            offset, cfg.d_target, cfg.kp, cfg.kd, self._prev_error
        )
        self._prev_error = error

        # 2. Predictive avoidance
        repulsive_sum = 0.0
        nearest_dist = float("inf")

        for ent in entities:
            # Skip the ego node — it doesn't repel itself
            if getattr(ent, "is_ego", False):
                continue

            xp, yp = lat.predict_position(
                ent.x, ent.y, ent.vx, ent.vy, cfg.lookahead_t
            )
            dist = math.sqrt(xp**2 + yp**2)
            if dist < nearest_dist:
                nearest_dist = dist

            # Area entities use distributed sampling
            if getattr(ent, "entity_type", None) == "area" and (ent.extent_x > 0 or ent.extent_y > 0):
                s_i = lat.compute_area_repulsive_vector(
                    xp,
                    yp,
                    ent.extent_x,
                    ent.extent_y,
                    ent.smoothed_certainty,
                    ent.danger_quality,
                    cfg.epsilon,
                    cfg.alpha_decay,
                    ent.danger_class,
                )
            else:
                s_i = lat.compute_repulsive_vector(
                    xp,
                    yp,
                    ent.smoothed_certainty,
                    ent.danger_quality,
                    cfg.epsilon,
                    cfg.alpha_decay,
                    ent.danger_class,
                )
            vortex = lat.compute_vortex_component(s_i, cfg.vortex_gain)
            repulsive_sum += s_i + vortex

        # 3. Vector resolution
        w_eff = lat.compute_adaptive_w_rep(
            nearest_dist,
            cfg.w_rep,
            cfg.adaptive_rep_min,
            cfg.adaptive_rep_max,
            cfg.adaptive_rep_range,
        )
        delta_theta = lat.resolve_steering(
            a_edge,
            repulsive_sum,
            w_eff,
            cfg.theta_max,
            self._prev_theta,
            cfg.theta_rate_max,
        )
        self._prev_theta = delta_theta

        # ── B. Longitudinal (Velocity) ─────────────────────────────────

        corridor = lon.build_safety_corridor(
            vehicle.v_current,
            cfg.theta_max,
            cfg.machine_width,
            cfg.corridor_length_factor,
        )

        predicted_entities: list[tuple[float, float, float, float, bool]] = []
        for ent in entities:
            if getattr(ent, "is_ego", False):
                continue
            xp, yp = lat.predict_position(
                ent.x, ent.y, ent.vx, ent.vy, cfg.lookahead_t
            )
            is_in = lon.in_corridor(xp, yp, corridor)
            predicted_entities.append(
                (xp, yp, ent.smoothed_certainty, ent.danger_quality, is_in)
            )

        v_target = lon.compute_target_velocity(
            predicted_entities, cfg.v_base, cfg.v_max
        )

        # ── C. Visualization ───────────────────────────────────────────
        viz_json = None
        if render_viz:
            from agri_nav.viz.viz_apf_field import plot_apf_field
            # Call plot function with show=False so it returns the figure
            fig = plot_apf_field(entities, crop_grid, vehicle, cfg, show=False)
            viz_json = fig.to_json()

        return ControlOutput(
            steering=SteeringCommand(delta_theta=delta_theta),
            velocity=VelocityCommand(v_target=v_target),
            frontend_viz_json=viz_json,
        )

    def reset(self) -> None:
        """Clear all internal state (e.g. after an e-stop)."""
        self._prev_theta = 0.0
        self._prev_error = 0.0
