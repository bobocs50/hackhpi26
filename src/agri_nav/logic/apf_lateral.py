"""Lateral (steering) APF control — pure functions.

Implements crop-contour tracking, predictive repulsive vectors with
exponential decay and vortex component, and final vector resolution
with rate limiting.
"""

from __future__ import annotations

import math

import numpy as np

from agri_nav.dto.config import APFConfig
from agri_nav.dto.perception import DangerClass


# ---------------------------------------------------------------------------
# 1. Crop Contour Tracking
# ---------------------------------------------------------------------------


def compute_crop_gradient(grid_data: np.ndarray, resolution: float) -> np.ndarray:
    """Compute the spatial gradient ∇P_crop of the crop occupancy grid.

    Returns an (rows, cols, 2) array where [..., 0] is dP/dx and [..., 1]
    is dP/dy, both in *world-frame* units (probability / metre).
    """
    # np.gradient returns (dy, dx) for a 2-D array
    gy, gx = np.gradient(grid_data, resolution)
    return np.stack([gx, gy], axis=-1)


def find_edge_offset(
    gradient: np.ndarray,
    vehicle_col: int,
    vehicle_row: int,
    resolution: float,
) -> float:
    """Estimate the lateral (x) distance from the vehicle to the crop edge.

    The crop edge is the row at ``vehicle_row`` where the gradient
    magnitude is maximal.  Returns a signed distance in metres
    (positive = edge is to the right of the vehicle).
    """
    row_grad = gradient[vehicle_row, :, :]  # (cols, 2)
    magnitudes = np.linalg.norm(row_grad, axis=-1)

    edge_col = int(np.argmax(magnitudes))
    return (edge_col - vehicle_col) * resolution


def compute_attractive_vector(
    current_offset: float,
    d_target: float,
    kp: float,
    kd: float,
    prev_error: float,
) -> tuple[float, float]:
    """PD controller producing an attractive steering vector A_edge.

    Parameters
    ----------
    current_offset:
        Current lateral distance to the crop edge [m].
    d_target:
        Desired lateral offset [m].
    kp, kd:
        Proportional / derivative gains.
    prev_error:
        Cross-track error from the previous tick for the D-term.

    Returns
    -------
    (a_edge, error):
        Steering contribution and current error (to feed back next tick).
    """
    error = d_target - current_offset
    derivative = error - prev_error
    a_edge = kp * error + kd * derivative
    return a_edge, error


# ---------------------------------------------------------------------------
# 2. Predictive Avoidance
# ---------------------------------------------------------------------------


def predict_position(
    x: float, y: float, vx: float, vy: float, t: float
) -> tuple[float, float]:
    """Project an entity's position forward by *t* seconds.

    P_predicted = (x + vx·t,  y + vy·t)
    """
    return x + vx * t, y + vy * t


def compute_repulsive_vector(
    x_pred: float,
    y_pred: float,
    certainty: float,
    danger_quality: float,
    epsilon: float,
    alpha: float,
    danger_class: DangerClass = DangerClass.MUST_AVOID,
) -> float:
    """Compute a single repulsive steering contribution S_i.

    Uses exponential distance-decay (improvement #3) and class-aware
    scaling (improvement #6).

    S_i = -sgn(x_pred) · (c·q / (dist + ε)) · exp(-α · y_pred)
    """
    dist = math.sqrt(x_pred**2 + y_pred**2) + epsilon

    # Class-aware scaling: crossable entities are weaker, targets ignored
    class_scale = _class_scale(danger_class)

    magnitude = (certainty * danger_quality / dist) * math.exp(
        -alpha * max(y_pred, 0.0)
    )
    sign = -1.0 if x_pred >= 0 else 1.0
    return sign * magnitude * class_scale


def compute_vortex_component(repulsive_value: float, vortex_gain: float) -> float:
    """Add a tangential (perpendicular) vector to break symmetry.

    Improvement #2: a small component perpendicular to the repulsive
    direction helps steer *around* obstacles instead of oscillating.
    """
    return vortex_gain * abs(repulsive_value)


def compute_area_repulsive_vector(
    x_center: float,
    y_center: float,
    extent_x: float,
    extent_y: float,
    certainty: float,
    danger_quality: float,
    epsilon: float,
    alpha: float,
    danger_class: DangerClass = DangerClass.MUST_AVOID,
    n_samples: int = 5,
) -> float:
    """Compute distributed repulsion from an area entity.

    Instead of a single point source, samples the repulsive potential
    over a grid of ``n_samples × n_samples`` points within the entity's
    bounding box, producing a smoother, wider force field.

    Returns the averaged lateral repulsive contribution.
    """
    total = 0.0
    count = 0

    for ix in range(n_samples):
        for iy in range(n_samples):
            # Uniformly sample within the extent
            sx = x_center - extent_x + (2 * extent_x * ix / max(1, n_samples - 1))
            sy = y_center - extent_y + (2 * extent_y * iy / max(1, n_samples - 1))

            total += compute_repulsive_vector(
                sx, sy, certainty, danger_quality, epsilon, alpha, danger_class
            )
            count += 1

    return total / max(1, count)


# ---------------------------------------------------------------------------
# 3. Vector Resolution
# ---------------------------------------------------------------------------


def compute_adaptive_w_rep(
    nearest_distance: float,
    w_rep: float,
    rep_min: float,
    rep_max: float,
    rep_range: float,
) -> float:
    """Scale W_rep inversely with nearest-hazard distance (improvement #1).

    Interpolates linearly between rep_max (at distance=0) and rep_min
    (at distance >= rep_range), then multiplies by the base w_rep.
    """
    t = min(max(nearest_distance / rep_range, 0.0), 1.0)
    multiplier = rep_max + t * (rep_min - rep_max)
    return w_rep * multiplier


def resolve_steering(
    a_edge: float,
    repulsive_sum: float,
    w_rep_effective: float,
    theta_max: float,
    prev_theta: float,
    theta_rate_max: float,
) -> float:
    """Combine vectors, clamp magnitude, then apply rate limiter.

    Δθ = clamp( A_edge + W_rep · Σ S_i ,  -θ_max, θ_max )
    then |Δθ_t - Δθ_{t-1}| ≤ θ_rate_max   (improvement #4)
    """
    raw = a_edge + w_rep_effective * repulsive_sum

    # Magnitude clamp
    clamped = max(-theta_max, min(theta_max, raw))

    # Rate limiter (improvement #4)
    delta = clamped - prev_theta
    if abs(delta) > theta_rate_max:
        clamped = prev_theta + math.copysign(theta_rate_max, delta)

    return clamped


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _class_scale(danger_class: DangerClass) -> float:
    """Return a multiplier based on entity danger class (improvement #6)."""
    if danger_class == DangerClass.CROSSABLE:
        return 0.2
    if danger_class == DangerClass.TARGET:
        return 0.0  # targets produce no repulsion
    return 1.0  # MUST_AVOID
