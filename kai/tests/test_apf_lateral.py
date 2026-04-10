"""Tests for APF lateral control (apf_lateral.py)."""

import math

import numpy as np
import pytest

from agri_nav.dto.perception import DangerClass
from agri_nav.logic.apf_lateral import (
    compute_adaptive_w_rep,
    compute_attractive_vector,
    compute_crop_gradient,
    compute_repulsive_vector,
    compute_vortex_component,
    find_edge_offset,
    predict_position,
    resolve_steering,
)


# ---------------------------------------------------------------------------
# Crop contour tracking
# ---------------------------------------------------------------------------


class TestCropGradient:
    def test_uniform_grid_has_zero_gradient(self) -> None:
        grid = np.ones((10, 10))
        grad = compute_crop_gradient(grid, resolution=0.5)
        np.testing.assert_allclose(grad, 0.0, atol=1e-12)

    def test_gradient_shape(self) -> None:
        grid = np.random.rand(20, 30)
        grad = compute_crop_gradient(grid, resolution=1.0)
        assert grad.shape == (20, 30, 2)

    def test_linear_ramp_has_constant_gradient(self) -> None:
        """A grid linearly increasing along x should have constant dP/dx."""
        grid = np.tile(np.arange(10, dtype=float), (5, 1))  # (5, 10)
        grad = compute_crop_gradient(grid, resolution=1.0)
        # Interior dP/dx ≈ 1.0
        np.testing.assert_allclose(grad[2, 2:-2, 0], 1.0, atol=1e-12)


class TestFindEdgeOffset:
    def test_edge_directly_at_vehicle(self) -> None:
        grad = np.zeros((5, 10, 2))
        grad[2, 5, :] = [10.0, 10.0]  # peak at col 5
        offset = find_edge_offset(grad, vehicle_col=5, vehicle_row=2, resolution=1.0)
        assert offset == 0.0

    def test_edge_to_the_right(self) -> None:
        grad = np.zeros((5, 10, 2))
        grad[2, 8, :] = [10.0, 10.0]
        offset = find_edge_offset(grad, vehicle_col=3, vehicle_row=2, resolution=0.5)
        assert offset == pytest.approx(2.5)


class TestAttractiveVector:
    def test_no_error_gives_zero(self) -> None:
        a_edge, err = compute_attractive_vector(
            current_offset=1.5, d_target=1.5, kp=1.0, kd=0.3, prev_error=0.0
        )
        assert a_edge == pytest.approx(0.0)
        assert err == pytest.approx(0.0)

    def test_positive_error_steers_toward_edge(self) -> None:
        a_edge, _ = compute_attractive_vector(
            current_offset=0.5, d_target=1.5, kp=1.0, kd=0.0, prev_error=0.0
        )
        assert a_edge > 0  # steers right toward the edge


# ---------------------------------------------------------------------------
# Predictive avoidance
# ---------------------------------------------------------------------------


class TestPredictPosition:
    def test_static_entity(self) -> None:
        xp, yp = predict_position(1.0, 2.0, 0.0, 0.0, t=1.0)
        assert (xp, yp) == (1.0, 2.0)

    def test_moving_entity(self) -> None:
        xp, yp = predict_position(0.0, 0.0, 1.0, 2.0, t=0.5)
        assert xp == pytest.approx(0.5)
        assert yp == pytest.approx(1.0)


class TestRepulsiveVector:
    def test_entity_on_right_steers_left(self) -> None:
        s = compute_repulsive_vector(
            x_pred=2.0, y_pred=3.0, certainty=0.9, danger_quality=0.8,
            epsilon=0.01, alpha=0.5,
        )
        assert s < 0  # negative = steer left

    def test_entity_on_left_steers_right(self) -> None:
        s = compute_repulsive_vector(
            x_pred=-2.0, y_pred=3.0, certainty=0.9, danger_quality=0.8,
            epsilon=0.01, alpha=0.5,
        )
        assert s > 0

    def test_crossable_is_weaker(self) -> None:
        s_avoid = abs(compute_repulsive_vector(
            2.0, 3.0, 0.9, 0.8, 0.01, 0.5, DangerClass.MUST_AVOID
        ))
        s_cross = abs(compute_repulsive_vector(
            2.0, 3.0, 0.9, 0.8, 0.01, 0.5, DangerClass.CROSSABLE
        ))
        assert s_cross < s_avoid

    def test_target_produces_zero(self) -> None:
        s = compute_repulsive_vector(
            2.0, 3.0, 0.9, 0.8, 0.01, 0.5, DangerClass.TARGET
        )
        assert s == 0.0


class TestVortexComponent:
    def test_positive_repulsion(self) -> None:
        v = compute_vortex_component(-0.5, vortex_gain=0.15)
        assert v == pytest.approx(0.075)

    def test_zero_gain(self) -> None:
        v = compute_vortex_component(-0.5, vortex_gain=0.0)
        assert v == 0.0


# ---------------------------------------------------------------------------
# Vector resolution
# ---------------------------------------------------------------------------


class TestAdaptiveWRep:
    def test_at_zero_distance(self) -> None:
        w = compute_adaptive_w_rep(0.0, 1.0, rep_min=0.5, rep_max=3.0, rep_range=10.0)
        assert w == pytest.approx(3.0)

    def test_at_max_range(self) -> None:
        w = compute_adaptive_w_rep(10.0, 1.0, rep_min=0.5, rep_max=3.0, rep_range=10.0)
        assert w == pytest.approx(0.5)

    def test_beyond_range_clamps(self) -> None:
        w = compute_adaptive_w_rep(50.0, 1.0, rep_min=0.5, rep_max=3.0, rep_range=10.0)
        assert w == pytest.approx(0.5)


class TestResolveSteering:
    def test_clamps_to_theta_max(self) -> None:
        theta = resolve_steering(
            a_edge=100.0, repulsive_sum=0.0, w_rep_effective=1.0,
            theta_max=0.5, prev_theta=0.0, theta_rate_max=1.0,
        )
        assert theta == pytest.approx(0.5)

    def test_rate_limiter(self) -> None:
        theta = resolve_steering(
            a_edge=0.5, repulsive_sum=0.0, w_rep_effective=1.0,
            theta_max=0.5, prev_theta=0.0, theta_rate_max=0.1,
        )
        # Rate limit: can only move 0.1 from prev_theta=0.0
        assert theta == pytest.approx(0.1)

    def test_negative_clamp(self) -> None:
        theta = resolve_steering(
            a_edge=-100.0, repulsive_sum=0.0, w_rep_effective=1.0,
            theta_max=0.5, prev_theta=0.0, theta_rate_max=1.0,
        )
        assert theta == pytest.approx(-0.5)
