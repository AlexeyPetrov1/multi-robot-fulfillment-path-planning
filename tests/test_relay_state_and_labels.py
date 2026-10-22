"""Checkpoint planning retains physical state; readable names round-trip."""

from dataclasses import replace

import pytest

from robotics.relay.model import Scenario
from robotics.relay.planner import RelayCoordinator
from robotics.relay.simulator import ActionRejected, MissionSimulator, transition
from tests.test_relay_simulator import mission


def test_optional_labels_roundtrip_and_appear_on_snapshot_tasks():
    data = mission(tasks=1)
    data["nodes"][0]["label"] = "Склад Север"
    data["tasks"][0]["label"] = "Заказ 01"
    scenario = Scenario.from_dict(data)
    payload = scenario.to_dict()
    assert scenario.nodes[0].label == payload["nodes"][0]["label"] == "Склад Север"
    assert scenario.tasks[0].label == payload["tasks"][0]["label"] == "Заказ 01"
    assert Scenario.from_dict(payload).to_dict() == payload
    assert MissionSimulator(scenario).snapshot()["tasks"][0]["label"] == "Заказ 01"
    assert "label" not in payload["nodes"][1]


def test_unlabeled_scenarios_keep_the_existing_serialized_shape():
    scenario = Scenario.from_dict(mission())
    assert all("label" not in row for key in ("nodes", "tasks")
               for row in scenario.to_dict()[key])
    assert "label" not in MissionSimulator(scenario).snapshot()["tasks"][0]


@pytest.mark.parametrize("key", ["nodes", "tasks"])
@pytest.mark.parametrize("label", ["", "  ", 5, False, []])
def test_labels_must_be_nonempty_strings_when_provided(key, label):
    data = mission()
    data[key][0]["label"] = label
    with pytest.raises(ValueError, match="label"):
        Scenario.from_dict(data)


def test_planning_continues_after_a_real_handoff_without_resetting_energy():
    sim = MissionSimulator(Scenario.from_dict(mission(tasks=1)))
    sim.step({"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "C", "R2": "C"},
              "transfers": [{"task": "T1", "from": "R1", "to": "R2"}]})
    checkpoint = sim.state
    result = RelayCoordinator(sim.scenario).plan(initial_state=checkpoint, max_timesteps=2)
    assert result.success and result.optimal and len(result.actions) == 2
    state = checkpoint
    for action in result.actions:
        assert not action.get("pickups")
        state = transition(sim.scenario, state, action)
    assert state.owners == (-2,) and state.positions == ("A", "E")
    assert state.batteries == (16, 16)
    assert sim.state == checkpoint and sim.timestep == 2
    assert RelayCoordinator(sim.scenario).plan(initial_state=checkpoint,
                                               max_timesteps=1).status == "horizon_limit"
    assert RelayCoordinator(sim.scenario).plan(initial_state=state,
                                               max_timesteps=0).actions == []


def test_checkpoint_cannot_forge_a_handoff_for_a_pending_task():
    scenario = Scenario.from_dict(mission(tasks=1))
    forged = replace(scenario.initial_state(), handed=(True,))
    with pytest.raises(ActionRejected) as error:
        RelayCoordinator(scenario).plan(initial_state=forged)
    assert error.value.code == "invalid_state"


def test_checkpoint_cannot_restore_previously_unavailable_initial_energy():
    data = mission(tasks=1)
    data["robots"][0]["battery"] = 10
    scenario = Scenario.from_dict(data)
    forged = replace(scenario.initial_state(), batteries=(20, 20))
    with pytest.raises(ActionRejected) as error:
        RelayCoordinator(scenario).plan(initial_state=forged)
    assert error.value.code == "invalid_state"
