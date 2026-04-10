"""Tests for SGG processor (sgg_processor.py)."""

import pytest

from agri_nav.dto.config import SGGConfig
from agri_nav.dto.perception import DangerClass, KinematicsEntity, SemanticEntity
from agri_nav.logic.sgg_processor import (
    classify_danger,
    merge_perception,
    smooth_certainty,
)


# ---------------------------------------------------------------------------
# Danger classification
# ---------------------------------------------------------------------------


class TestClassifyDanger:
    THRESHOLDS = {DangerClass.CROSSABLE: 0.3, DangerClass.MUST_AVOID: 0.7}

    def test_low_quality_is_crossable(self) -> None:
        assert classify_danger(0.1, self.THRESHOLDS) == DangerClass.CROSSABLE

    def test_boundary_crossable(self) -> None:
        assert classify_danger(0.3, self.THRESHOLDS) == DangerClass.CROSSABLE

    def test_mid_quality_is_target(self) -> None:
        assert classify_danger(0.5, self.THRESHOLDS) == DangerClass.TARGET

    def test_high_quality_is_must_avoid(self) -> None:
        assert classify_danger(0.9, self.THRESHOLDS) == DangerClass.MUST_AVOID

    def test_boundary_must_avoid(self) -> None:
        assert classify_danger(0.7, self.THRESHOLDS) == DangerClass.MUST_AVOID


# ---------------------------------------------------------------------------
# Temporal smoothing
# ---------------------------------------------------------------------------


class TestSmoothCertainty:
    def test_first_observation(self) -> None:
        # With prev == current, result == current
        result = smooth_certainty(0.8, 0.8, ema_alpha=0.3)
        assert result == pytest.approx(0.8)

    def test_smoothing_effect(self) -> None:
        # α=0.3: result = 0.3*1.0 + 0.7*0.5 = 0.65
        result = smooth_certainty(1.0, 0.5, ema_alpha=0.3)
        assert result == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# Merge perception
# ---------------------------------------------------------------------------


class TestMergePerception:
    def _make_kin(self, id: int, cls: str = "person") -> KinematicsEntity:
        return KinematicsEntity(id=id, cls=cls, x=1.0, y=2.0, vx=0.0, vy=0.0)

    def _make_sem(self, id: int, c: float = 0.9, q: float = 0.8) -> SemanticEntity:
        return SemanticEntity(id=id, certainty=c, danger_quality=q)

    def test_inner_join(self) -> None:
        kins = [self._make_kin(1), self._make_kin(2)]
        sems = [self._make_sem(1)]
        result = merge_perception(kins, sems, SGGConfig())
        assert len(result) == 1
        assert result[0].id == 1

    def test_classification_applied(self) -> None:
        kins = [self._make_kin(1)]
        sems = [self._make_sem(1, q=0.1)]  # low danger
        result = merge_perception(kins, sems, SGGConfig())
        assert result[0].danger_class == DangerClass.CROSSABLE

    def test_ema_with_prev_smoothed(self) -> None:
        kins = [self._make_kin(1)]
        sems = [self._make_sem(1, c=1.0, q=0.8)]
        cfg = SGGConfig(ema_alpha=0.3)
        result = merge_perception(kins, sems, cfg, prev_smoothed={1: 0.5})
        # 0.3*1.0 + 0.7*0.5 = 0.65
        assert result[0].smoothed_certainty == pytest.approx(0.65)

    def test_empty_inputs(self) -> None:
        result = merge_perception([], [], SGGConfig())
        assert result == []
