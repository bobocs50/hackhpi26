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
        _is_rollout: bool = False,
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
        delta_theta_raw = lat.resolve_steering(
            a_edge,
            repulsive_sum,
            w_eff,
            cfg.theta_max,
            self._prev_theta,
            cfg.theta_rate_max,
        )

        trajectory = None
        if not _is_rollout:
            # Generate the physics-based trajectory curve
            trajectory = self._predict_trajectory(entities, crop_grid, vehicle, steps=20, dt=0.15)
            
            # Pure pursuit: target a point on the smoothed trajectory
            lookahead_steps = 4  # e.g., 0.6 seconds ahead
            target_idx = min(lookahead_steps, len(trajectory) - 1)
            
            if len(trajectory) > target_idx:
                tx, ty, _ = trajectory[target_idx]
                dx = tx - vehicle.x
                dy = ty - vehicle.y
                
                # Global target heading
                target_heading = math.atan2(dx, dy)
                
                # Delta relative to current heading
                delta = target_heading - vehicle.heading
                # Normalize to [-pi, pi]
                delta = (delta + math.pi) % (2 * math.pi) - math.pi
                
                # Clamp to max steering angle limit
                delta = max(-cfg.theta_max, min(cfg.theta_max, delta))
                
                # Apply rate limit
                max_change = cfg.theta_rate_max
                delta_theta = max(self._prev_theta - max_change, min(self._prev_theta + max_change, delta))
            else:
                delta_theta = delta_theta_raw
        else:
            delta_theta = delta_theta_raw

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
        viz_data = None
        if render_viz:
            from agri_nav.dto.visualization import APFVisualData, APFEntityViz

            if trajectory is None:
                trajectory = self._predict_trajectory(entities, crop_grid, vehicle, steps=40, dt=0.15)
            
            # Simple downsampled mesh generation to reduce payload size
            # 20m x 20m area with 0.5m resolution
            import numpy as np
            extent = 12.0
            res = 0.5
            x_vals = np.arange(-extent, extent, res).tolist()
            y_vals = np.arange(-2, extent * 1.5, res).tolist()
            z_raw = self._compute_potential_surface(np.array(x_vals), np.array(y_vals), entities, cfg)
            z_log = np.log1p(z_raw).tolist()

            viz_entities = []
            for ent in entities:
                if getattr(ent, "is_ego", False):
                    continue
                xp, yp = lat.predict_position(ent.x, ent.y, ent.vx, ent.vy, cfg.lookahead_t)
                ttc_str = f"{ent.ttc:.1f}s" if ent.ttc != float('inf') else "∞"
                color = "#e74c3c" if ent.danger_class.name == "MUST_AVOID" else ("#2ecc71" if ent.danger_class.name == "CROSSABLE" else "#f39c12")
                viz_entities.append(APFEntityViz(
                    id=ent.id, cls=ent.cls, x=xp, y=yp, z=0.0,
                    color=color, danger_quality=ent.danger_quality,
                    smoothed_certainty=ent.smoothed_certainty,
                    ttc_label=ttc_str, danger_class=ent.danger_class.value
                ))

            viz_data = APFVisualData(
                x_grid=x_vals,
                y_grid=y_vals,
                z_surface=z_log,
                ego_x=vehicle.x,
                ego_y=vehicle.y,
                ego_v=vehicle.v_current,
                entities=viz_entities,
                extent_x=extent,
                extent_y=extent * 1.5,
                control_steer_x=math.sin(delta_theta) * 2.0,
                control_steer_y=math.cos(delta_theta) * v_target,
                delta_theta=delta_theta,
                v_target=v_target,
                trajectory=trajectory,
                corridor_xy=[(c[0] + vehicle.x, c[1] + vehicle.y) for c in corridor.exterior.coords],
            )

        return ControlOutput(
            steering=SteeringCommand(delta_theta=delta_theta),
            velocity=VelocityCommand(v_target=v_target),
            visual_data=viz_data,
        )

    def _compute_potential_surface(self, x_range, y_range, entities, cfg):
        import numpy as np
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

            # Continuous scale: proportional to danger_quality
            # CROSSABLE entities get dampened, all others scale with their actual danger
            if ent.danger_class.name == "CROSSABLE":
                scale = 0.2 * ent.danger_quality
            else:
                scale = max(ent.danger_quality, 0.05)  # floor to keep entities visible

            Z += scale * (ent.smoothed_certainty / dist) * decay

        return Z

    def _predict_trajectory(
        self,
        entities: list[TrackedEntity],
        crop_grid: CropOccupancyGrid,
        vehicle: VehicleState,
        steps: int = 20,
        dt: float = 0.15,
    ) -> list[tuple[float, float, float]]:
        """Adam-optimized contour-constrained trajectory rollout.

        Uses a modified Adam optimizer to adaptively scale the integration step:
        - **First moment (m)**: exponential moving average of the displacement
          gradient → smoothed direction (replaces simple momentum).
        - **Second moment (v)**: exponential moving average of squared gradient
          → per-axis adaptive step scaling. Steps shrink near high-curvature
          obstacle walls and grow in flat, safe regions.

        Contour constraint (iso-contour sliding) is preserved when
        U(x,y) >= traj_max_potential.

        Adam hyperparameters (β₁=0.9, β₂=0.999, ε=1e-8) are standard defaults.
        """

        cfg = self._cfg

        sim_svc = APFService(cfg)
        sim_svc._prev_error = self._prev_error
        sim_svc._prev_theta = self._prev_theta

        sim_veh = VehicleState(vehicle.x, vehicle.y, vehicle.v_current, vehicle.heading)
        sim_ents = [TrackedEntity(**e.model_dump()) for e in entities]

        raw_traj = [(sim_veh.x, sim_veh.y, 0.0)]
        omega = 0.0

        # Numerical gradient delta
        h = 0.05

        # Adam state
        beta1 = cfg.traj_adam_beta1
        beta2 = cfg.traj_adam_beta2
        adam_eps = cfg.traj_adam_eps
        m_x, m_y = 0.0, 0.0  # first moment (mean of gradients)
        v_x, v_y = 0.0, 0.0  # second moment (mean of squared gradients)
        base_lr = cfg.traj_adam_lr  # Base spatial step length [m]

        for step_i in range(1, steps + 1):
            out = sim_svc.compute(sim_ents, crop_grid, sim_veh, render_viz=False, _is_rollout=True)

            # -- Momentum-regularized steering --
            raw_delta = out.steering.delta_theta
            forward_pull = -cfg.traj_forward_bias * sim_veh.heading
            target_omega = raw_delta + forward_pull
            omega = cfg.traj_momentum * omega + (1.0 - cfg.traj_momentum) * target_omega
            omega *= cfg.traj_heading_damping

            sim_veh.heading += omega * dt
            sim_veh.heading = max(-cfg.theta_max * 2, min(cfg.theta_max * 2, sim_veh.heading))

            v_speed = out.velocity.v_target

            # Raw displacement gradient (desired direction × speed)
            g_x = v_speed * math.sin(sim_veh.heading)
            g_y = v_speed * math.cos(sim_veh.heading)

            # Adam moment updates
            m_x = beta1 * m_x + (1 - beta1) * g_x
            m_y = beta1 * m_y + (1 - beta1) * g_y
            v_x = beta2 * v_x + (1 - beta2) * g_x**2
            v_y = beta2 * v_y + (1 - beta2) * g_y**2

            # Bias-corrected estimates
            m_hat_x = m_x / (1 - beta1**step_i)
            m_hat_y = m_y / (1 - beta1**step_i)
            v_hat_x = v_x / (1 - beta2**step_i)
            v_hat_y = v_y / (1 - beta2**step_i)

            # Adam-scaled step: adaptive per-axis
            dx_raw = base_lr * m_hat_x / (math.sqrt(v_hat_x) + adam_eps)
            dy_raw = base_lr * m_hat_y / (math.sqrt(v_hat_y) + adam_eps)

            # -- Contour constraint --
            cand_x = sim_veh.x + dx_raw
            cand_y = sim_veh.y + dy_raw
            U_cand = self._eval_potential_at(cand_x, cand_y, sim_ents, cfg)

            if cfg.traj_max_potential > 0 and U_cand > cfg.traj_max_potential:
                # Project onto iso-contour tangent
                U_px = self._eval_potential_at(cand_x + h, cand_y, sim_ents, cfg)
                U_mx = self._eval_potential_at(cand_x - h, cand_y, sim_ents, cfg)
                U_py = self._eval_potential_at(cand_x, cand_y + h, sim_ents, cfg)
                U_my = self._eval_potential_at(cand_x, cand_y - h, sim_ents, cfg)

                grad_x = (U_px - U_mx) / (2 * h)
                grad_y = (U_py - U_my) / (2 * h)
                grad_mag = math.sqrt(grad_x**2 + grad_y**2)

                if grad_mag > 1e-6:
                    tang_x1, tang_y1 = -grad_y / grad_mag, grad_x / grad_mag
                    tang_x2, tang_y2 = grad_y / grad_mag, -grad_x / grad_mag

                    dot1 = tang_x1 * dx_raw + tang_y1 * dy_raw
                    dot2 = tang_x2 * dx_raw + tang_y2 * dy_raw

                    if dot1 >= dot2:
                        tang_x, tang_y = tang_x1, tang_y1
                        proj_scale = dot1
                    else:
                        tang_x, tang_y = tang_x2, tang_y2
                        proj_scale = dot2

                    proj_scale = max(proj_scale, 0.0)
                    dx_raw = tang_x * proj_scale
                    dy_raw = tang_y * proj_scale

                    if proj_scale > 1e-6:
                        sim_veh.heading = math.atan2(dx_raw / dt, dy_raw / dt)

            sim_veh.x += dx_raw
            sim_veh.y += dy_raw
            sim_veh.v_current = v_speed

            # Transform entities into the new ego-relative frame
            d_theta_step = omega * dt
            cos_t = math.cos(-d_theta_step)
            sin_t = math.sin(-d_theta_step)
            next_ents = []
            for ent in sim_ents:
                nx = ent.x
                ny = ent.y - (v_speed * dt)
                new_x = nx * cos_t - ny * sin_t + ent.vx * dt
                new_y = nx * sin_t + ny * cos_t + ent.vy * dt
                next_ents.append(TrackedEntity(**{**ent.model_dump(), "x": new_x, "y": new_y}))
            sim_ents = next_ents

            raw_traj.append((sim_veh.x, sim_veh.y, 0.0))

        # -- Gaussian kernel smoothing ----------------------------------------
        n = len(raw_traj)
        if n < 5:
            return raw_traj

        kernel_size = min(7, n // 2)
        sigma = kernel_size / 3.0
        kernel = [math.exp(-0.5 * ((i - kernel_size) / sigma) ** 2)
                  for i in range(2 * kernel_size + 1)]
        k_sum = sum(kernel)
        kernel = [k / k_sum for k in kernel]

        xs = [p[0] for p in raw_traj]
        ys = [p[1] for p in raw_traj]

        smooth_xs = list(xs)
        for i in range(kernel_size, n - kernel_size):
            acc = 0.0
            for j, k_val in enumerate(kernel):
                acc += xs[i - kernel_size + j] * k_val
            smooth_xs[i] = acc

        traj = [(smooth_xs[i], ys[i], 0.0) for i in range(n)]
        return traj

    def _eval_potential_at(
        self,
        px: float,
        py: float,
        entities: list[TrackedEntity],
        cfg: "APFConfig",
    ) -> float:
        """Evaluate the scalar potential U = log1p(raw_repulsion) at a single point."""
        U = 0.0
        for ent in entities:
            if getattr(ent, "is_ego", False):
                continue
            xp, yp = lat.predict_position(ent.x, ent.y, ent.vx, ent.vy, cfg.lookahead_t)
            dx = px - xp
            dy = py - yp
            dist = math.sqrt(dx**2 + dy**2) + cfg.epsilon
            decay = math.exp(-cfg.alpha_decay * max(dy, 0.0))

            if ent.danger_class.name == "CROSSABLE":
                scale = 0.2 * ent.danger_quality
            else:
                scale = max(ent.danger_quality, 0.05)

            U += scale * (ent.smoothed_certainty / dist) * decay

        return math.log1p(U)

    def reset(self) -> None:
        """Clear all internal state (e.g. after an e-stop)."""
        self._prev_theta = 0.0
        self._prev_error = 0.0
