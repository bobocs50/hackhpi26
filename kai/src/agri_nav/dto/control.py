"""Pydantic models for control outputs sent to vehicle actuators."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SteeringCommand(BaseModel):
    """Lateral control output — steering angle delta."""

    model_config = ConfigDict(frozen=True)

    delta_theta: float = Field(description="Steering angle change [rad]")


class VelocityCommand(BaseModel):
    """Longitudinal control output — target velocity."""

    model_config = ConfigDict(frozen=True)

    v_target: float = Field(ge=0.0, description="Target velocity [m/s]")


class ControlOutput(BaseModel):
    """Combined control output for a single tick."""

    model_config = ConfigDict(frozen=True)

    steering: SteeringCommand
    velocity: VelocityCommand
    frontend_viz_json: str | None = Field(
        default=None,
        description="Serialized Plotly Figure JSON for UI rendering, if generated",
    )
