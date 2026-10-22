"""A short warehouse shift uses the same rolling policy as the 25-job case."""

import json
from collections import Counter
from math import floor
from pathlib import Path

import pytest

from robotics.relay.model import Scenario
from robotics.services.relay_service import replay_mission


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def prepared():
    data = json.loads((ROOT / "scenarios/grid16_team4.json").read_text(encoding="utf-8"))
    actions = json.loads((ROOT / "scenarios/plans/grid16_team4.actions.json").read_text(encoding="utf-8"))
    return data, actions, Scenario.from_dict(data), replay_mission(data, actions)


def test_four_jobs_are_a_named_subset_on_the_complete_unit_grid(prepared):
    data, _, world, _ = prepared
    from scripts.build_grid16_team4_25 import specification

    assert len(world.nodes) == 256 and len(world.edges) == 480
    assert len(world.robots) == len(world.tasks) == 4
    assert all(edge.cost == 1 for edge in world.edges)
    assert data["tasks"] == specification(25)["tasks"][:4]
    assert all(task.label for task in world.tasks)


def test_even_arbitrary_solo_assignment_cannot_cover_all_four_jobs(prepared):
    data, _, world, _ = prepared
    for task in world.tasks:
        assert world.distance(task.pickup, task.dropoff) == 22
        for following in world.tasks:
            assert world.distance(task.dropoff, following.pickup) == 22
    budgets = [floor((robot.battery - robot.capacity * 0.1) / robot.move_cost + 1e-8)
               for robot in world.robots]
    assert budgets == [84, 40, 70, 70]
    assert [budget // 44 for budget in budgets] == [1, 0, 1, 1]
    assert data["no_handoff_bound"]["maximum_team_jobs"] == 3 < len(world.tasks)


def test_policy_delivers_once_to_empty_couriers_and_preserves_energy(prepared):
    _, actions, world, report = prepared
    assert report["success"] and report["status"] == "completed"
    transfers = [event for event in report["events"] if event["type"] == "transfer"]
    assert Counter(event["task"] for event in transfers) == {task.id: 1 for task in world.tasks}
    assert {event[key] for event in transfers for key in ("from", "to")} == {robot.id for robot in world.robots}
    for action, before, after in zip(actions, report["snapshots"], report["snapshots"][1:]):
        old = {robot["id"]: robot for robot in before["robots"]}
        for transfer in action.get("transfers", []):
            assert old[transfer["to"]]["cargo"] is None
        for left, right in zip(before["robots"], after["robots"]):
            assert right["battery"] <= left["battery"]
            assert right["battery"] + 1e-8 >= right["return_required"] + right["reserve"]
    assert all(robot["position"] == robot["station"] for robot in report["snapshots"][-1]["robots"])
    assert all(task["handed"] and task["status"] == "delivered" for task in report["snapshots"][-1]["tasks"])


def test_generator_reproduces_the_checked_short_plan(prepared):
    from scripts.build_grid16_team4_25 import build

    data, actions, _, _ = prepared
    assert build(4) == (data, actions)
