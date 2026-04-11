"""Tests for TTC-based SGG inference (sgg_inference.py)."""

import math

import pytest

from agri_nav.dto.perception import KinematicsEntity
from agri_nav.logic.sgg_inference import (
    SGGInferenceConfig,
    compute_certainty,
    compute_danger_quality,
    compute_ttc,
    infer_semantics,
)


# ---------------------------------------------------------------------------
# Certainty
# ---------------------------------------------------------------------------


class TestComputeCertainty:
    def test_brand_new_track_is_low(self):
        """track_age=0 → maturity = 0 → certainty = 0."""
        assert compute_certainty(0.95, track_age=0, lambda_track=0.15) == pytest.approx(0.0)

    def test_mature_track_converges(self):
        """Very old track → maturity ≈ 1 → certainty ≈ detection_confidence."""
        c = compute_certainty(0.9, track_age=200, lambda_track=0.15)
        assert c == pytest.approx(0.9, abs=0.01)

    def test_mid_age_track(self):
        """track_age=10, λ=0.15: maturity = 1 - e^(-1.5) ≈ 0.7769."""
        expected = 0.85 * (1 - math.exp(-1.5))
        assert compute_certainty(0.85, 10, 0.15) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# TTC
# ---------------------------------------------------------------------------


class TestComputeTTC:
    def test_entity_moving_away(self):
        """Entity moving away → TTC = inf."""
        ttc = compute_ttc(x=2.0, y=5.0, vx=0.0, vy=1.0, ego_vx=0.0, ego_vy=0.0, epsilon=0.1)
        assert ttc == float("inf")

    def test_entity_approaching_head_on(self):
        """Entity at y=10, vy=-2, ego vy=3 → closing speed = 5, dist=10 → TTC=2."""
        ttc = compute_ttc(x=0.0, y=10.0, vx=0.0, vy=-2.0, ego_vx=0.0, ego_vy=3.0, epsilon=0.1)
        assert ttc == pytest.approx(2.0)

    def test_stationary_entity_with_ego_moving(self):
        """Static entity ahead, ego moving forward → positive closing speed."""
        ttc = compute_ttc(x=0.0, y=6.0, vx=0.0, vy=0.0, ego_vx=0.0, ego_vy=3.0, epsilon=0.1)
        assert ttc == pytest.approx(2.0)

    def test_entity_at_origin(self):
        """Entity at ego position → TTC = 0 (immediate collision)."""
        ttc = compute_ttc(x=0.0, y=0.0, vx=0.0, vy=0.0, ego_vx=0.0, ego_vy=0.0, epsilon=0.1)
        assert ttc == 0.0

    def test_lateral_approach(self):
        """Entity approaching from the side."""
        ttc = compute_ttc(x=5.0, y=0.0, vx=-2.0, vy=0.0, ego_vx=0.0, ego_vy=0.0, epsilon=0.1)
        assert ttc == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Danger quality
# ---------------------------------------------------------------------------


class TestComputeDangerQuality:
    def test_immediate_collision_max_weight(self):
        """TTC=0, human (W=100) → q = 1.0."""
        q = compute_danger_quality(ttc=0.0, class_weight=100.0, max_weight=100.0, k_decay=0.5)
        assert q == pytest.approx(1.0)

    def test_far_away_decays(self):
        """Large TTC → q ≈ 0."""
        q = compute_danger_quality(ttc=100.0, class_weight=100.0, max_weight=100.0, k_decay=0.5)
        assert q < 0.001

    def test_low_weight_class(self):
        """Bush (W=5) at TTC=0 → q = 5/100 = 0.05."""
        q = compute_danger_quality(ttc=0.0, class_weight=5.0, max_weight=100.0, k_decay=0.5)
        assert q == pytest.approx(0.05)

    def test_inf_ttc(self):
        """Entity moving away → TTC = inf → q = 0."""
        q = compute_danger_quality(ttc=float("inf"), class_weight=100.0, max_weight=100.0, k_decay=0.5)
        assert q == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Full inference
# ---------------------------------------------------------------------------


class TestInferSemantics:
    def test_returns_one_per_entity(self):
        kins = [
            KinematicsEntity(id=1, cls="human", x=1.0, y=5.0, vx=0.0, vy=-1.0, detection_confidence=0.9, track_age=20),
            KinematicsEntity(id=2, cls="bush", x=3.0, y=2.0, vx=0.0, vy=0.0, detection_confidence=0.7, track_age=50),
        ]
        sems = infer_semantics(kins)
        assert len(sems) == 2
        assert sems[0].id == 1

    def test_human_more_dangerous_than_bush(self):
        """Human approaching ego should have higher danger than a static bush."""
        kins = [
            KinematicsEntity(id=1, cls="human", x=0.0, y=5.0, vx=0.0, vy=-2.0, detection_confidence=0.95, track_age=30),
            KinematicsEntity(id=2, cls="bush", x=3.0, y=2.0, vx=0.0, vy=0.0, detection_confidence=0.7, track_age=50),
        ]
        cfg = SGGInferenceConfig(ego_vy=3.0)
        sems = infer_semantics(kins, cfg)
        assert sems[0].danger_quality > sems[1].danger_quality

    def test_values_in_valid_range(self):
        kins = [
            KinematicsEntity(id=1, cls="deer", x=-1.0, y=6.0, vx=0.8, vy=-0.3, detection_confidence=0.85, track_age=8),
        ]
        sems = infer_semantics(kins, SGGInferenceConfig(ego_vy=3.0))
        assert 0.0 <= sems[0].certainty <= 1.0
        assert 0.0 <= sems[0].danger_quality <= 1.0

    def test_unknown_class_uses_default_weight(self):
        kins = [
            KinematicsEntity(id=1, cls="alien_spaceship", x=0.0, y=5.0, vx=0.0, vy=-1.0, detection_confidence=0.9, track_age=20),
        ]
        sems = infer_semantics(kins)
        assert sems[0].danger_quality > 0
