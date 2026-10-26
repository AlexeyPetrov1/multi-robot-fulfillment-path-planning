"""Mission acceptance is delivery, mandatory handoff, and everyone's safe return."""

from copy import deepcopy

import pytest

from robotics.relay.examples import example_scenarios
from robotics.services.relay_service import plan_mission, replay_mission


def test_three_robots_are_needed_and_everyone_returns():
    scenario = example_scenarios()["energy_relay"]
    report = plan_mission(scenario, max_timesteps=12, time_limit=30)
    assert report["success"], report
    assert report["status"] == "optimal"
    assert report["metrics"]["delivered_tasks"] == 1
    assert report["metrics"]["all_home"]
    assert report["metrics"]["transfer_count"] >= 2
    assert report["metrics"]["timesteps"] == 10
    assert report["metrics"]["total_energy"] == pytest.approx(40)
    assert all(len(s["robots"]) == 3 for s in report["snapshots"])
    final = report["snapshots"][-1]
    assert all(r["position"] == r["station"] for r in final["robots"])
    assert all(r["battery"] >= r["capacity"] * 0.1 for r in final["robots"])
    transfers = [e for e in report["events"] if e["type"] == "transfer"]
    assert {e["from"] for e in transfers} | {e["to"] for e in transfers} == {"R1", "R2", "R3"}
    for frame in report["snapshots"]:
        for robot in frame["robots"]:
            assert robot["battery"] + 1e-8 >= robot["return_required"]


@pytest.mark.parametrize("absent", ["R1", "R2", "R3"])
def test_energy_relay_cannot_be_completed_without_any_one_robot(absent):
    scenario = deepcopy(example_scenarios()["energy_relay"])
    scenario["robots"] = [r for r in scenario["robots"] if r["id"] != absent]
    report = plan_mission(scenario, max_timesteps=40, time_limit=15)
    assert not report["success"]
    assert report["status"] == "no_plan", report
    assert report["metrics"]["timesteps"] == 0
    assert report["snapshots"][0] == report["snapshots"][-1]


def test_passport_ring_delivers_both_tasks_with_real_exchange():
    report = plan_mission(example_scenarios()["passport_ring"], max_timesteps=8, time_limit=20)
    assert report["success"], report
    assert report["metrics"]["delivered_tasks"] == 2
    assert report["metrics"]["timesteps"] == 6
    assert report["metrics"]["total_energy"] == 23
    assert report["metrics"]["all_home"]
    assert all(t["handed"] for t in report["snapshots"][-1]["tasks"])
    occupied_twice = []
    for frame in report["snapshots"]:
        positions = [r["position"] for r in frame["robots"]]
        if len(set(positions)) != len(positions):
            occupied_twice.append(frame["timestep"])
    assert occupied_twice
    assert all(any(e["type"] == "transfer" and e["timestep"] == t for e in report["events"])
               for t in occupied_twice)
    for event in (e for e in report["events"] if e["type"] == "transfer"):
        before = report["snapshots"][event["timestep"] - 1]
        receiver = next(r for r in before["robots"] if r["id"] == event["to"])
        assert receiver["cargo"] is None


def test_plan_can_be_replayed_from_exported_actions():
    scenario = example_scenarios()["passport_ring"]
    planned = plan_mission(scenario, max_timesteps=8)
    replayed = replay_mission(scenario, planned["plan"]["actions"])
    assert replayed["success"]
    assert replayed["snapshots"] == planned["snapshots"]
    assert replayed["metrics"] == planned["metrics"]


def test_replay_rejects_invalid_action_without_moving_any_robot():
    report = replay_mission(example_scenarios()["passport_ring"], [{"moves": {"R1": "v4"}}])
    assert not report["success"]
    assert report["status"] == "rejected"
    assert report["metrics"]["timesteps"] == 0
    assert len(report["snapshots"]) == 1
    assert report["events"][-1]["type"] == "rejected"
    assert report["events"][-1]["code"]


def test_unfinished_plan_does_not_claim_delivery_success():
    scenario = example_scenarios()["energy_relay"]
    planned = plan_mission(scenario, max_timesteps=12, time_limit=30)
    report = replay_mission(scenario, planned["plan"]["actions"][:-1])
    assert report["metrics"]["delivered_tasks"] == 1
    assert not report["metrics"]["all_home"]
    assert not report["success"]
    assert report["status"] == "incomplete"


def test_low_energy_is_reported_as_refusal_and_preserves_initial_state():
    report = plan_mission(example_scenarios()["insufficient_energy"], max_timesteps=12)
    assert not report["success"]
    assert report["status"] == "no_plan", report
    assert report["metrics"]["timesteps"] == 0
    assert any(e["type"] == "refusal" for e in report["events"])


def test_horizon_limit_is_not_reported_as_global_impossibility():
    report = plan_mission(example_scenarios()["energy_relay"], max_timesteps=1)
    assert not report["success"]
    assert report["status"] == "horizon_limit"
