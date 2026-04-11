"""Longitudinal (velocity) APF control — pure functions.

Implements the safety-corridor construction, corridor membership test,
and braking protocol.
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon


# ---------------------------------------------------------------------------
# 1. Safety Corridor
# ---------------------------------------------------------------------------


def build_safety_corridor(
    v_current: float,
    theta_max: float,
    machine_width: float,
    corridor_length_factor: float,
) -> Polygon:
    """Build a forward-facing trapezoidal safety corridor.

    Improvement #5: corridor length scales with ``v_current`` (not the
    constant ``v_base``), so the lookahead shrinks as the machine slows.

    The corridor is symmetric about the y-axis (forward axis).  Its rear
    edge sits at y=0 and the front edge at y = factor * v_current.
    The front edge is wider than the rear edge by ``2 * corridor_length *
    tan(theta_max)`` to account for maximum possible lateral travel.

    Returns a Shapely Polygon in vehicle-local coordinates.
    """
    corridor_length = max(corridor_length_factor * v_current, 0.5)  # min 0.5 m
    half_w = machine_width / 2.0

    spread = corridor_length * math.tan(min(theta_max, math.pi / 4))

    # Trapezoid: bottom-left, bottom-right, top-right, top-left
    return Polygon(
        [
            (-half_w, 0.0),
            (half_w, 0.0),
            (half_w + spread, corridor_length),
            (-half_w - spread, corridor_length),
        ]
    )


def in_corridor(x: float, y: float, corridor: Polygon) -> bool:
    """Return True if the point (x, y) lies inside the safety corridor."""
    return corridor.contains(Point(x, y))


# ---------------------------------------------------------------------------
# 2. Braking Protocol
# ---------------------------------------------------------------------------


def compute_target_velocity(
    predicted_entities: list[tuple[float, float, float, float, bool]],
    v_base: float,
    v_max: float,
) -> float:
    """Compute V_target using the most critical in-corridor hazard.

    Parameters
    ----------
    predicted_entities:
        Each tuple is ``(x_pred, y_pred, certainty, danger_quality,
        is_in_corridor)``.
    v_base:
        Nominal forward velocity [m/s].
    v_max:
        Maximum allowed velocity [m/s].

    Returns
    -------
    Clamped target velocity in [0, v_max].

    The formula from the spec:
        V_target = V_base · (1 − max_i( c_i · q_i / y_pred_i · InCorridor ))
    """
    max_threat = 0.0

    for x_pred, y_pred, c_i, q_i, is_in in predicted_entities:
        if not is_in:
            continue
        if y_pred <= 0.0:
            # Entity is behind us — ignore
            continue
        threat = (c_i * q_i) / y_pred
        max_threat = max(max_threat, threat)

    v_target = v_base * (1.0 - min(max_threat, 1.0))
    return max(0.0, min(v_target, v_max))
