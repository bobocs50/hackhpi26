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
# Certainty: c_i = Conf_YOLO · (1 − e^(−λ · Age))
# ---------------------------------------------------------------------------


class TestComputeCertainty:
    def test_brand_new_track_is_low(self) -> None:
        """track_age=0 → maturity = 0 → certainty = 0."""
        assert compute_certainty(0.95, track_age=0, lambda_track=0.15) == pytest.approx(0.0)

    def test_mature_track_converges(self) -> None:
        """Very old track → maturity ≈ 1 → certainty ≈ detection_confidence."""
        c = compute_certainty(0.90, track_age=200, lambda_track=0.15)
        assert c == pytest.approx(0.90, abs=0.01)

    def test_mid_age_track(self) -> None:
        """track_age=10, λ=0.15: maturity = 1 - e^(-1.5) ≈ 0.7769."""
        expected = 0.85 * (1 - math.exp(-0.15 * 10))
        assert compute_certainty(0.85, 10, 0.15) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# TTC: dist / max(ε, closing_speed)
# ---------------------------------------------------------------------------


class TestComputeTTC:
    def test_entity_moving_away(self) -> None:
        """Entity moving away → TTC = inf."""
        ttc = compute_ttc(x=2.0, y=5.0, vx=0.0, vy=1.0, ego_vx=0.0, ego_vy=0.0, epsilon=0.1)
        assert ttc == float("inf")

    def test_entity_approaching_head_on(self) -> None:
        """Entity at y=10, vy=-2, ego vy=3 → closing speed = 5, dist=10 → TTC=2."""
        ttc = compute_ttc(x=0.0, y=10.0, vx=0.0, vy=-2.0, ego_vx=0.0, ego_vy=3.0, epsilon=0.1)
        assert ttc == pytest.approx(2.0)

    def test_stationary_entity_with_ego_moving(self) -> None:
        """Static entity ahead, ego moving forward → positive closing speed."""
        ttc = compute_ttc(x=0.0, y=6.0, vx=0.0, vy=0.0, ego_vx=0.0, ego_vy=3.0, epsilon=0.1)
        assert ttc == pytest.approx(2.0)

    def test_entity_at_origin(self) -> None:
        """Entity at ego position → TTC = 0 (immediate collision)."""
        ttc = compute_ttc(x=0.0, y=0.0, vx=0.0, vy=0.0, ego_vx=0.0, ego_vy=0.0, epsilon=0.1)
        assert ttc == 0.0

    def test_lateral_approach(self) -> None:
        """Entity approaching from the side."""
        # Entity at x=5, moving left (vx=-2) toward ego at origin
        ttc = compute_ttc(x=5.0, y=0.0, vx=-2.0, vy=0.0, ego_vx=0.0, ego_vy=0.0, epsilon=0.1)
        assert ttc == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Danger quality: (W_class / W_max) · e^(−k · TTC)
# ---------------------------------------------------------------------------


class TestComputeDangerQuality:
    def test_immediate_collision_max_weight(self) -> None:
        """TTC=0, human (W=100) → q = 1.0."""
        q = compute_danger_quality(ttc=0.0, class_weight=100.0, max_weight=100.0, k_decay=0.5)
        assert q == pytest.approx(1.0)

    def test_far_away_decays(self) -> None:
        """Large TTC → q ≈ 0."""
        q = compute_danger_quality(ttc=100.0, class_weight=100.0, max_weight=100.0, k_decay=0.5)
        assert q < 0.001

    def test_low_weight_class(self) -> None:
        """Bush (W=5) at TTC=0 → q = 5/100 = 0.05."""
        q = compute_danger_quality(ttc=0.0, class_weight=5.0, max_weight=100.0, k_decay=0.5)
        assert q == pytest.approx(0.05)

    def test_inf_ttc(self) -> None:
        """Entity moving away → TTC = inf → q = 0."""
        q = compute_danger_quality(ttc=float("inf"), class_weight=100.0, max_weight=100.0, k_decay=0.5)
        assert q == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# End-to-end: infer_semantics
# ---------------------------------------------------------------------------


class TestInferSemantics:
    def test_returns_one_per_entity(self) -> None:
        kins = [
            KinematicsEntity(id=1, cls="human", x=1.0, y=5.0, vx=0.0, vy=-1.0,
                             detection_confidence=0.9, track_age=20),
            KinematicsEntity(id=2, cls="bush", x=3.0, y=2.0, vx=0.0, vy=0.0,
                             detection_confidence=0.7, track_age=50),
        ]
        sems = infer_semantics(kins)
        assert len(sems) == 2
        assert sems[0].id == 1
        assert sems[1].id == 2

    def test_human_more_dangerous_than_bush(self) -> None:
        """Human approaching ego should have higher danger than a static bush."""
        kins = [
            KinematicsEntity(id=1, cls="human", x=0.0, y=5.0, vx=0.0, vy=-2.0,
                             detection_confidence=0.95, track_age=30),
            KinematicsEntity(id=2, cls="bush", x=3.0, y=3.0, vx=0.0, vy=0.0,
                             detection_confidence=0.70, track_age=30),
        ]
        cfg = SGGInferenceConfig(ego_vy=3.0)
        sems = infer_semantics(kins, cfg)
        assert sems[0].danger_quality > sems[1].danger_quality

    def test_values_in_valid_range(self) -> None:
        kins = [
            KinematicsEntity(id=1, cls="deer", x=-1.0, y=6.0, vx=0.8, vy=-0.3,
                             detection_confidence=0.85, track_age=8),
        ]
        sems = infer_semantics(kins, SGGInferenceConfig(ego_vy=3.0))
        assert 0.0 <= sems[0].certainty <= 1.0
        assert 0.0 <= sems[0].danger_quality <= 1.0

    def test_unknown_class_uses_default_weight(self) -> None:
        kins = [
            KinematicsEntity(id=1, cls="alien_spaceship", x=0.0, y=5.0, vx=0.0, vy=-1.0,
                             detection_confidence=0.9, track_age=20),
        ]
        sems = infer_semantics(kins)
        assert sems[0].danger_quality > 0  # default weight = 20, not 0
