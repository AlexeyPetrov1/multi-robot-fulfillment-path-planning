"""Robots outside a joint move remain physical obstacles."""

import pytest

from robotics.coordination.coordinated_executor import CoordinatedExecutor
from robotics.coordination.coordinator import MultiRobotCoordinator
from robotics.robots.robot import Robot
from robotics.robots.robot_state import RobotStatus
from robotics.simulation.simulator import WarehouseSimulator
from robotics.warehouse.grid import Position as P
from robotics.warehouse.warehouse import Warehouse


def _sim(warehouse, starts):
    sim = WarehouseSimulator(warehouse)
    for rid, position in starts.items():
        sim.add_robot(Robot(rid, position))
    return sim


def _execute(kind, sim, plan):
    if kind == "plain":
        return CoordinatedExecutor(sim).execute(plan)
    from robotics.recovery.recovery_manager import RecoveryManager

    return RecoveryManager(sim).run(plan)


@pytest.mark.parametrize("kind", ["plain", "recovery"])
@pytest.mark.parametrize("status", [RobotStatus.IDLE, RobotStatus.OFFLINE])
def test_unplanned_robot_blocks_whole_joint_step(kind, status):
    warehouse = Warehouse(width=4, height=3)
    starts = {"R1": P(0, 0), "R2": P(2, 0)}
    plan = MultiRobotCoordinator(warehouse).plan(
        starts, {"R1": P(0, 2), "R2": P(2, 2)}
    )
    sim = _sim(warehouse, {**starts, "parked": P(0, 1)})
    sim.get_robot("parked").set_status(status)

    result = _execute(kind, sim, plan)

    assert not result.success
    assert result.total_move_steps == 0
    assert sim.get_robot("R1").position == starts["R1"]
    assert sim.get_robot("R2").position == starts["R2"]
    assert sim.get_robot("parked").position == P(0, 1)


@pytest.mark.parametrize("kind", ["plain", "recovery"])
def test_failed_plan_does_not_remove_robot_from_the_world(kind):
    warehouse = Warehouse(width=6, height=1)
    starts = {"R1": P(0, 0), "R2": P(0, 5)}
    plan = MultiRobotCoordinator(warehouse).plan(
        starts, {"R1": P(0, 5), "R2": P(0, 0)}
    )
    assert plan.failed_robot_ids == ["R2"]
    sim = _sim(warehouse, starts)

    result = _execute(kind, sim, plan)

    assert not result.success
    assert sim.get_robot("R2").position == P(0, 5)
    assert sim.get_robot("R1").position != P(0, 5)
    assert len(sim.occupied_cells()) == len(sim.robots)
    assert result.validation_problems == []


@pytest.mark.parametrize("kind", ["plain", "recovery"])
def test_joint_move_may_enter_a_cell_another_robot_vacates(kind):
    warehouse = Warehouse(width=5, height=1)
    starts = {"R1": P(0, 1), "R2": P(0, 0)}
    plan = MultiRobotCoordinator(warehouse).plan(
        starts, {"R1": P(0, 4), "R2": P(0, 3)}
    )
    sim = _sim(warehouse, starts)

    result = _execute(kind, sim, plan)

    assert result.success
    assert sim.get_robot("R1").position == P(0, 4)
    assert sim.get_robot("R2").position == P(0, 3)


@pytest.mark.parametrize("recovery_enabled", [True, False])
def test_robot_stopped_by_obstacle_remains_occupied(recovery_enabled):
    from robotics.recovery.disruption import DisruptionSchedule, DynamicObstacleEvent
    from robotics.recovery.recovery_manager import RecoveryManager

    warehouse = Warehouse(width=6, height=1)
    starts = {"R1": P(0, 2), "R2": P(0, 0)}
    plan = MultiRobotCoordinator(warehouse).plan(
        starts, {"R1": P(0, 5), "R2": P(0, 3)}
    )
    sim = _sim(warehouse, starts)

    result = RecoveryManager(sim).run(
        plan,
        DisruptionSchedule.of(DynamicObstacleEvent(0, P(0, 4))),
        recovery_enabled=recovery_enabled,
    )

    assert result.safe_stop
    assert sim.get_robot("R1").position == P(0, 2)
    assert sim.get_robot("R2").position == P(0, 1)
    assert result.validation_problems == []


def test_recovery_routes_around_an_unplanned_robot(monkeypatch):
    from robotics.recovery.disruption import DisruptionSchedule, DynamicObstacleEvent
    from robotics.recovery.recovery_manager import RecoveryManager

    warehouse = Warehouse(width=5, height=3)
    starts = {"R1": P(1, 0)}
    plan = MultiRobotCoordinator(warehouse).plan(starts, {"R1": P(1, 4)})
    sim = _sim(warehouse, {**starts, "parked": P(0, 2)})
    visited = []
    move_to = sim.get_robot("R1").move_to

    def record_move(destination):
        visited.append(destination)
        move_to(destination)

    monkeypatch.setattr(sim.get_robot("R1"), "move_to", record_move)

    result = RecoveryManager(sim).run(
        plan, DisruptionSchedule.of(DynamicObstacleEvent(0, P(1, 2)))
    )

    assert result.success
    assert sim.get_robot("R1").position == P(1, 4)
    assert sim.get_robot("parked").position == P(0, 2)
    assert P(0, 2) not in visited
    assert result.validation_problems == []
