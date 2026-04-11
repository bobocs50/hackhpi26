"""Tuning-parameter models for APF and SGG subsystems."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agri_nav.dto.perception import DangerClass


class APFConfig(BaseModel):
    """All tunable knobs for the Artificial Potential Field controllers."""

    # --- Lateral (steering) ---
    theta_max: float = Field(
        default=0.5, gt=0.0, description="Max absolute steering angle [rad]"
    )
    theta_rate_max: float = Field(
        default=0.1,
        gt=0.0,
        description="Max steering change per tick [rad] (improvement #4)",
    )
    w_rep: float = Field(
        default=1.0, gt=0.0, description="Global repulsion weight"
    )
    epsilon: float = Field(
        default=0.01,
        gt=0.0,
        description="Small constant to prevent division by zero",
    )
    alpha_decay: float = Field(
        default=0.5,
        gt=0.0,
        description="Exponential decay rate for distance falloff (improvement #3)",
    )
    vortex_gain: float = Field(
        default=0.15,
        ge=0.0,
        description="Tangential vortex component gain (improvement #2)",
    )
    d_target: float = Field(
        default=1.5, gt=0.0, description="Desired lateral offset from crop edge [m]"
    )
    kp: float = Field(
        default=1.0, description="PD proportional gain for contour tracking"
    )
    kd: float = Field(
        default=0.3, description="PD derivative gain for contour tracking"
    )
    lookahead_t: float = Field(
        default=1.0,
        gt=0.0,
        description="Hazard position lookahead time [s]",
    )

    # --- Longitudinal (velocity) ---
    v_base: float = Field(
        default=3.0, gt=0.0, description="Nominal forward velocity [m/s]"
    )
    v_max: float = Field(
        default=5.0, gt=0.0, description="Maximum forward velocity [m/s]"
    )
    machine_width: float = Field(
        default=3.0, gt=0.0, description="Machine width [m]"
    )
    corridor_length_factor: float = Field(
        default=2.0,
        gt=0.0,
        description="Corridor length = factor * v_current (improvement #5)",
    )

    # --- Adaptive repulsion (improvement #1) ---
    adaptive_rep_min: float = Field(
        default=0.5,
        ge=0.0,
        description="Minimum W_rep multiplier when hazards are far",
    )
    adaptive_rep_max: float = Field(
        default=3.0,
        gt=0.0,
        description="Maximum W_rep multiplier when hazards are close",
    )
    adaptive_rep_range: float = Field(
        default=10.0,
        gt=0.0,
        description="Distance [m] at which multiplier = adaptive_rep_min",
    )

    # --- Trajectory prediction regularization ---
    traj_momentum: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "Heading momentum coefficient (0=no inertia, 1=full inertia). "
            "Blends previous heading change with new steering command."
        ),
    )
    traj_forward_bias: float = Field(
        default=0.3,
        ge=0.0,
        description=(
            "Attractive pull towards straight-ahead (heading=0). "
            "Higher values penalize lateral deviation more strongly."
        ),
    )
    traj_heading_damping: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description=(
            "Exponential damping on accumulated heading angular velocity. "
            "Acts as friction to prevent oscillation."
        ),
    )
    traj_safety_offset: float = Field(
        default=0.8,
        ge=0.0,
        description=(
            "Vertical offset below the gradient maximum [m]. "
            "The trajectory follows a contour this far below the peak repulsion, "
            "acting as an adjustable safety margin."
        ),
    )
    traj_max_potential: float = Field(
        default=0.05,
        ge=0.0,
        description=(
            "Maximum log1p(U) potential value the vehicle is willing to enter."
        ),
    )
    traj_adam_lr: float = Field(
        default=0.35,
        ge=0.01,
        description="Base spatial step size (learning rate) for the Adam trajectory rollout [m]. Replaces raw v*dt.",
    )
    traj_adam_beta1: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Adam first moment decay (momentum). Smooths the displacement direction.",
    )
    traj_adam_beta2: float = Field(
        default=0.999,
        ge=0.0,
        le=1.0,
        description="Adam second moment decay (variance). Adaptively scales step size based on curvature.",
    )
    traj_adam_eps: float = Field(
        default=1e-8,
        ge=0.0,
        description="Adam epsilon to prevent division by zero.",
    )


class SGGConfig(BaseModel):
    """Tunable knobs for Scene-Graph-Generation processing."""

    ema_alpha: float = Field(
        default=0.3,
        gt=0.0,
        le=1.0,
        description="EMA smoothing factor for certainty (improvement #7)",
    )
    danger_thresholds: dict[DangerClass, float] = Field(
        default={
            DangerClass.CROSSABLE: 0.3,
            DangerClass.MUST_AVOID: 0.7,
        },
        description=(
            "danger_quality <= CROSSABLE threshold → crossable; "
            ">= MUST_AVOID threshold → must_avoid; else target (improvement #6)"
        ),
    )
