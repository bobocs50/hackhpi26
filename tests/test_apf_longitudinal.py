"""Tests for APF longitudinal control (apf_longitudinal.py)."""

import math

import pytest

from agri_nav.logic.apf_longitudinal import (
    build_safety_corridor,
    compute_target_velocity,
    in_corridor,
)


# ---------------------------------------------------------------------------
# Safety corridor
# ---------------------------------------------------------------------------


class TestBuildSafetyCorridor:
    def test_corridor_is_valid_polygon(self):
        poly = build_safety_corridor(
            v_current=3.0, theta_max=0.5, machine_width=2.0,
            corridor_length_factor=3.0,
        )
        assert poly.is_valid
        assert poly.area > 0

    def test_corridor_length_scales_with_velocity(self):
        slow = build_safety_corridor(1.0, 0.3, 3.0, 2.0)
        fast = build_safety_corridor(5.0, 0.3, 3.0, 2.0)
        assert fast.area > slow.area

    def test_zero_velocity_gets_minimum_corridor(self):
        poly = build_safety_corridor(0.0, 0.5, 3.0, 2.0)
        assert poly.is_valid
        assert poly.area > 0


class TestInCorridor:
    def test_point_directly_ahead(self):
        poly = build_safety_corridor(3.0, 0.5, 2.0, 3.0)
        assert in_corridor(0.0, 1.0, poly) is True

    def test_point_behind(self):
        poly = build_safety_corridor(3.0, 0.5, 2.0, 3.0)
        assert in_corridor(0.0, -1.0, poly) is False

    def test_point_far_lateral(self):
        poly = build_safety_corridor(3.0, 0.5, 2.0, 3.0)
        assert in_corridor(100.0, 1.0, poly) is False


# ---------------------------------------------------------------------------
# Braking protocol
# ---------------------------------------------------------------------------


class TestComputeTargetVelocity:
    def test_no_entities(self):
        v = compute_target_velocity([], v_base=3.0, v_max=5.0)
        assert v == pytest.approx(3.0)

    def test_entity_not_in_corridor(self):
        entities = [(10.0, 5.0, 0.9, 0.9, False)]
        v = compute_target_velocity(entities, v_base=3.0, v_max=5.0)
        assert v == pytest.approx(3.0)

    def test_entity_in_corridor_slows_down(self):
        entities = [(0.0, 3.0, 0.9, 0.9, True)]
        v = compute_target_velocity(entities, v_base=3.0, v_max=5.0)
        # threat = (0.9 * 0.9) / 3.0 = 0.27; v = 3.0 * (1 - 0.27)
        assert v == pytest.approx(3.0 * (1.0 - 0.27))

    def test_hard_brake_for_high_threat(self):
        entities = [(0.0, 0.5, 1.0, 1.0, True)]
        v = compute_target_velocity(entities, v_base=3.0, v_max=5.0)
        assert v == pytest.approx(0.0)

    def test_behind_entity_ignored(self):
        entities = [(0.0, -1.0, 1.0, 1.0, True)]
        v = compute_target_velocity(entities, v_base=3.0, v_max=5.0)
        assert v == pytest.approx(3.0)

    def test_velocity_clamped_to_vmax(self):
        v = compute_target_velocity([], v_base=10.0, v_max=5.0)
        assert v == pytest.approx(5.0)
