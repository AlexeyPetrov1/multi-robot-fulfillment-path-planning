"""A handoff has one carrier and one receiver who was empty before the tick."""

from copy import deepcopy

import pytest

from robotics.relay.model import Scenario, State
from robotics.relay.planner import RelayCoordinator
from robotics.relay.simulator import ActionRejected, MissionSimulator, transition
from tests.test_relay_simulator import approach, exchange, mission


def test_loaded_robots_cannot_swap_cargo_and_rejection_is_atomic():
    sim = MissionSimulator(Scenario.from_dict(mission()))
    approach(sim)
    before, snapshots = sim.state, deepcopy(sim.snapshots)
    with pytest.raises(ActionRejected) as error:
        sim.step(exchange())
    assert error.value.code == "receiver_loaded"
    assert sim.state == before and sim.timestep == 1
    assert sim.snapshots == snapshots


def test_delivering_during_the_tick_does_not_free_a_receiver():
    data = mission()
    data["tasks"][1]["dropoff"] = "C"
    scenario = Scenario.from_dict(data)
    state = State(("B", "D"), (19, 19), (0, 1), (False, True))
    with pytest.raises(ActionRejected) as error:
        transition(scenario, state, {
            "moves": {"R1": "C", "R2": "C"},
            "transfers": [{"task": "T1", "from": "R1", "to": "R2"}],
            "deliveries": ["T2"],
        })
    assert error.value.code == "receiver_loaded"


def test_receiver_cannot_pick_up_a_different_task_during_the_tick():
    data = mission()
    data["tasks"][1]["pickup"] = "D"
    scenario = Scenario.from_dict(data)
    state = State(("B", "D"), (19, 19), (0, -1), (False, False))
    with pytest.raises(ActionRejected) as error:
        transition(scenario, state, {
            "pickups": {"T2": "R2"}, "moves": {"R1": "C", "R2": "C"},
            "transfers": [{"task": "T1", "from": "R1", "to": "R2"}],
        })
    assert error.value.code == "receiver_loaded"


def test_one_robot_cannot_take_part_in_two_transfers_in_a_tick():
    data = mission()
    data["nodes"].append({"id": "X", "x": 2, "y": 1})
    data["edges"].append({"source": "X", "target": "C"})
    data["robots"].append({"id": "R3", "station": "X", "capacity": 20,
                           "battery": 20, "move_cost": 1})
    scenario = Scenario.from_dict(data)
    state = State(("B", "D", "X"), (19, 19, 20), (0, 1), (False, False))
    with pytest.raises(ActionRejected) as error:
        transition(scenario, state, {
            "moves": {"R1": "C", "R2": "C", "R3": "C"}, "transfers": [
                {"task": "T1", "from": "R1", "to": "R3"},
                {"task": "T2", "from": "R2", "to": "R3"},
            ],
        })
    assert error.value.code == "transfer_busy"


def test_arrival_and_handoff_share_one_tick_then_robots_depart():
    sim = MissionSimulator(Scenario.from_dict(mission(tasks=1)))
    sim.step({"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "C", "R2": "C"},
              "transfers": [{"task": "T1", "from": "R1", "to": "R2"}]})
    assert sim.timestep == 2 and sim.state.positions == ("C", "C")
    assert sim.state.owners == (1,) and sim.state.handed == (True,)
    assert sim.state.batteries == (18, 18)
    assert [r["cargo"] for r in sim.snapshot()["robots"]] == [None, "T1"]
    with pytest.raises(ActionRejected, match="valid transfer"):
        sim.step({})
    sim.step({"moves": {"R1": "B", "R2": "D"}})
    assert sim.state.positions == ("B", "D") and sim.timestep == 3


def test_exact_planner_handles_opposite_jobs_without_a_swap():
    scenario = Scenario.from_dict(mission())
    result = RelayCoordinator(scenario).plan(time_limit=20)
    assert result.success and result.optimal
    state = scenario.initial_state()
    for action in result.actions:
        for transfer in action.get("transfers", []):
            receiver = scenario.robot_index[transfer["to"]]
            assert receiver not in state.owners
        state = transition(scenario, state, action)
    assert state.owners == (-2, -2) and state.positions == ("A", "E")
