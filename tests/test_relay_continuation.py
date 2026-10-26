"""Resume a checked mission from its actual state, without resets or free energy."""

from copy import deepcopy

import pytest

from robotics.relay.examples import example_scenarios
from robotics.services import relay_service as service


def physical_frames(frames):
    return [{"timestep": f["timestep"], "tasks": f["tasks"], "complete": f["complete"],
             "robots": [{key: robot[key] for key in
                         ("id", "position", "battery", "cargo", "return_required", "reserve")}
                        for robot in f["robots"]]} for f in frames]


@pytest.fixture(scope="module")
def route():
    return service.plan_mission(example_scenarios()["energy_relay"], max_timesteps=15)


def test_resume_preserves_every_executed_tick_and_original_batteries(route):
    prefix = service.replay_mission(route["scenario"], route["plan"]["actions"][:3])
    resumed = service.continue_mission(prefix, max_timesteps=15)
    assert resumed["success"], resumed
    assert physical_frames(resumed["snapshots"][:4]) == physical_frames(prefix["snapshots"])
    assert resumed["plan"]["actions"][:3] == prefix["plan"]["actions"]
    assert resumed["metrics"]["timesteps"] == 10
    assert resumed["metrics"]["total_energy"] == 40
    assert resumed["status"] == "completed" and resumed["optimal"] is False
    assert resumed["plan"]["remaining_optimal"] is True
    for before, after in zip(resumed["snapshots"], resumed["snapshots"][1:]):
        assert all(b["battery"] <= a["battery"]
                   for a, b in zip(before["robots"], after["robots"]))


def test_resume_reconstructs_energy_from_actions_instead_of_trusting_a_report(route):
    prefix = service.replay_mission(route["scenario"], route["plan"]["actions"][:3])
    fake = deepcopy(prefix)
    fake["snapshots"][-1]["robots"][0]["battery"] = 10_000
    actual = service.continue_mission(fake, max_timesteps=15)
    assert actual["success"]
    assert physical_frames(actual["snapshots"][:4]) == physical_frames(prefix["snapshots"])
    assert actual["metrics"]["total_energy"] == 40


def test_resume_rejects_an_invalid_executed_prefix(route):
    invalid = service.replay_mission(route["scenario"], [{"moves": {"R1": "missing"}}])
    with pytest.raises(ValueError, match="rejected"):
        service.continue_mission(invalid, max_timesteps=15)


def test_completed_mission_is_not_started_again(route):
    continued = service.continue_mission(route, max_timesteps=15)
    assert continued["success"]
    assert continued["snapshots"] == route["snapshots"]
    assert continued["plan"]["actions"] == route["plan"]["actions"]


def test_next_destination_comes_from_checked_actions_and_changes_after_delivery(route):
    delivery = next(e for e in route["events"] if e["type"] == "delivery")
    frame = route["snapshots"][delivery["timestep"]]
    owner = next(e["to"] for e in reversed(route["events"])
                 if e["type"] == "transfer" and e["task"] == delivery["task"])
    robot = next(r for r in frame["robots"] if r["id"] == owner)
    assert robot["cargo"] is None
    assert robot["activity"] == "returning"
    assert robot["destination"] == robot["station"]
    assert all("destination_label" in r and "activity" in r
               for f in route["snapshots"] for r in f["robots"])


def test_unknown_planner_strategy_is_rejected():
    with pytest.raises(ValueError, match="strategy"):
        service.plan_mission(example_scenarios()["simple_handoff"], strategy="magic")
