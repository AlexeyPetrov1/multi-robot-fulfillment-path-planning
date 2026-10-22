"""Small gallery examples must demonstrate their advertised behaviour."""

import pytest

from robotics.relay.examples import example_actions, example_scenarios
from robotics.relay.model import Scenario
from robotics.relay.simulator import ActionRejected, transition
from robotics.services.relay_service import plan_mission, replay_mission


NAMES = ("simple_handoff", "waiting_partner", "energy_detour")


@pytest.fixture(scope="module")
def reports():
    examples = example_scenarios()
    return {name: replay_mission(examples[name], example_actions(name))
            if name == "waiting_partner" else plan_mission(examples[name]) for name in NAMES}


@pytest.mark.parametrize("name", NAMES)
def test_gallery_missions_finish_with_handoff_and_every_robot_home(reports, name):
    report = reports[name]
    assert report["success"]
    assert report["status"] == ("completed" if name == "waiting_partner" else "optimal")
    assert report["metrics"]["transfer_count"] == 1
    assert report["metrics"]["all_home"]
    assert all(task["handed"] for task in report["snapshots"][-1]["tasks"])
    for snapshot in report["snapshots"]:
        for robot in snapshot["robots"]:
            assert robot["battery"] + 1e-8 >= robot["return_required"] + robot["reserve"]


def test_simple_exchange_takes_two_joint_ticks(reports):
    report = reports["simple_handoff"]
    assert report["metrics"]["timesteps"] == 2
    assert report["metrics"]["total_energy"] == 4
    meeting = next(event for event in report["events"] if event["type"] == "transfer")
    assert meeting["timestep"] == 1
    assert {robot["position"] for robot in report["snapshots"][1]["robots"]} == {"M"}


def test_partner_really_waits_away_from_home_before_the_exchange(reports):
    report = reports["waiting_partner"]
    assert report["metrics"]["total_tasks"] == 1
    assert report["metrics"]["timesteps"] == 4
    assert report["metrics"]["total_energy"] == 6
    optimum = plan_mission(example_scenarios()["waiting_partner"])
    assert optimum["optimal"]
    assert optimum["metrics"]["timesteps"] == report["metrics"]["timesteps"]
    assert not report.get("optimal", False)
    meeting = next(event for event in report["events"] if event["type"] == "transfer")
    frame = report["snapshots"][meeting["timestep"]]
    meeting_vertex = next(robot["position"] for robot in frame["robots"]
                          if robot["id"] == meeting["from"])
    waits = [event for event in report["events"] if event["type"] == "wait"
             and event["timestep"] <= meeting["timestep"]
             and event["from"] == meeting_vertex]
    assert waits, "The example must show waiting for a partner, not waiting after returning home"
    receiver_before = next(r for r in report["snapshots"][meeting["timestep"] - 1]["robots"]
                           if r["id"] == meeting["to"])
    assert receiver_before["cargo"] is None
    for event in waits:
        robot = next(robot for robot in frame["robots"] if robot["id"] == event["robot"])
        assert event["from"] != robot["station"]


def test_detour_uses_the_longer_affordable_path_and_rejects_the_direct_edge(reports):
    report = reports["energy_detour"]
    assert report["metrics"]["timesteps"] == 4
    assert report["metrics"]["total_energy"] == 10
    moves = [event for event in report["events"] if event["type"] == "move"]
    assert len(moves) == 8
    assert all({event["from"], event["to"]} != {"A", "B"} for event in moves)
    assert [robot["battery"] for robot in report["snapshots"][-1]["robots"]] == [2, 2]
    scenario = Scenario.from_dict(example_scenarios()["energy_detour"])
    assert scenario.adjacency["A"]["B"] == 10
    assert scenario.distance("A", "B") == 4
    for robot, destination in (("R1", "B"), ("R2", "A")):
        with pytest.raises(ActionRejected) as caught:
            transition(scenario, scenario.initial_state(), {"moves": {robot: destination}})
        assert caught.value.code == "return_reserve"
