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
