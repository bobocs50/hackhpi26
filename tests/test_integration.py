"""Integration test — full APFService.compute() round-trip."""

import numpy as np
import pytest

from agri_nav.dto.config import APFConfig, SGGConfig
from agri_nav.dto.perception import CropOccupancyGrid, KinematicsEntity, SemanticEntity
from agri_nav.service.apf_service import APFService, VehicleState
from agri_nav.service.sgg_service import SGGService


@pytest.fixture
def crop_grid() -> CropOccupancyGrid:
    """A 20×20 grid with a clear crop edge at column 14."""
    data = np.ones((20, 20))
    data[:, 14:] = 0.0
    return CropOccupancyGrid(data=data, resolution=0.5, origin_x=0.0, origin_y=0.0)


@pytest.fixture
def vehicle() -> VehicleState:
    return VehicleState(x=5.0, y=3.0, v_current=3.0, heading=0.0)


@pytest.fixture
def sgg_service() -> SGGService:
    return SGGService()


@pytest.fixture
def apf_service() -> APFService:
    return APFService()


class TestIntegration:
    def test_no_obstacles_follows_contour(self, apf_service, crop_grid, vehicle, sgg_service):
        """With no obstacles, the vehicle should track the crop contour."""
        out_sgg = sgg_service.process([], [])
        out = apf_service.compute(out_sgg.nodes, crop_grid, vehicle)
        assert -apf_service._cfg.theta_max <= out.steering.delta_theta <= apf_service._cfg.theta_max
        assert out.velocity.v_target == pytest.approx(apf_service._cfg.v_base)

    def test_obstacle_ahead_causes_braking(self, apf_service, crop_grid, vehicle, sgg_service):
        """An obstacle directly ahead in the corridor should slow the vehicle."""
        kins = [KinematicsEntity(id=1, cls="person", x=0.0, y=3.0, vx=0.0, vy=0.0)]
        sems = [SemanticEntity(id=1, certainty=0.95, danger_quality=0.9)]
        out_sgg = sgg_service.process(kins, sems)
        out = apf_service.compute(out_sgg.nodes, crop_grid, vehicle)
        assert out.velocity.v_target < apf_service._cfg.v_base

    def test_hard_brake_for_imminent_human(self, apf_service, crop_grid, vehicle, sgg_service):
        """A human very close ahead with max certainty/quality → hard brake."""
        kins = [KinematicsEntity(id=1, cls="human", x=0.0, y=0.3, vx=0.0, vy=0.0)]
        sems = [SemanticEntity(id=1, certainty=1.0, danger_quality=1.0)]
        out_sgg = sgg_service.process(kins, sems)
        out = apf_service.compute(out_sgg.nodes, crop_grid, vehicle)
        assert out.velocity.v_target == pytest.approx(0.0)

    def test_output_within_physical_limits(self, apf_service, crop_grid, vehicle, sgg_service):
        """Run a multi-tick simulation and assert all outputs are legal."""
        kins = [
            KinematicsEntity(id=1, cls="bush", x=2.0, y=5.0, vx=-0.5, vy=-1.0),
            KinematicsEntity(id=2, cls="person", x=0.0, y=8.0, vx=-0.3, vy=0.0),
        ]
        sems = [
            SemanticEntity(id=1, certainty=0.6, danger_quality=0.2),
            SemanticEntity(id=2, certainty=0.85, danger_quality=0.95),
        ]
        cfg = apf_service._cfg

        for _ in range(10):
            out_sgg = sgg_service.process(kins, sems)
            out = apf_service.compute(out_sgg.nodes, crop_grid, vehicle)
            assert -cfg.theta_max <= out.steering.delta_theta <= cfg.theta_max
            assert 0.0 <= out.velocity.v_target <= cfg.v_max
