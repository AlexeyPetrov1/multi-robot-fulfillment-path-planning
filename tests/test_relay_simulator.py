"""Mission rules are checked against whole joint ticks, including rejected ones."""

from dataclasses import FrozenInstanceError
from math import inf

import pytest

from robotics.relay.model import Scenario, State
from robotics.relay.simulator import ActionRejected, MissionSimulator, transition


def mission(*, tasks=2, third=False):
    data = {
        "name": "exchange-line",
        "nodes": [{"id": node, "x": i, "y": 0} for i, node in enumerate("ABCDE")],
        "edges": [{"source": a, "target": b} for a, b in zip("ABCD", "BCDE")],
        "robots": [
            {"id": "R1", "start": "A", "station": "A", "capacity": 20,
             "battery": 20, "move_cost": 1},
            {"id": "R2", "start": "E", "station": "E", "capacity": 20,
             "battery": 20, "move_cost": 1},
        ],
        "tasks": [{"id": "T1", "pickup": "A", "dropoff": "E"},
                  {"id": "T2", "pickup": "E", "dropoff": "A"}][:tasks],
    }
    if third:
        data["robots"].append({"id": "R3", "start": "C", "station": "C",
                               "capacity": 20, "battery": 20, "move_cost": 1})
    return data


def approach(sim):
    sim.step({"pickups": {"T1": "R1", "T2": "R2"},
              "moves": {"R1": "B", "R2": "D"}})


def exchange():
    return {"moves": {"R1": "C", "R2": "C"}, "transfers": [
        {"task": "T1", "from": "R1", "to": "R2"},
        {"task": "T2", "from": "R2", "to": "R1"},
    ]}


def test_scenario_roundtrip_and_initial_state_are_explicit():
    data = mission()
    del data["robots"][0]["start"]
    scenario = Scenario.from_dict(data)
    assert Scenario.from_dict(scenario.to_dict()).to_dict() == scenario.to_dict()
    assert scenario.adjacency["A"]["B"] == scenario.adjacency["B"]["A"] == 1
    assert scenario.robot_index == {"R1": 0, "R2": 1}
    assert scenario.task_index == {"T1": 0, "T2": 1}
    assert scenario.initial_state() == State(("A", "E"), (20, 20), (-1, -1), (False, False))
    with pytest.raises(FrozenInstanceError):
        scenario.initial_state().positions = ("B", "E")


@pytest.mark.parametrize("kind", ["node", "robot", "task", "edge", "reference", "infinite",
                                 "negative_cost", "over_capacity", "below_reserve", "start"])
def test_scenario_rejects_invalid_input(kind):
    data = mission()
    if kind in {"node", "robot", "task", "edge"}:
        key = {"node": "nodes", "robot": "robots", "task": "tasks", "edge": "edges"}[kind]
        data[key].append(dict(data[key][0]))
    elif kind == "reference":
        data["tasks"][0]["pickup"] = "missing"
    elif kind == "infinite":
        data["nodes"][0]["x"] = inf
    elif kind == "negative_cost":
        data["edges"][0]["cost"] = -1
    elif kind == "over_capacity":
        data["robots"][0]["battery"] = 21
    elif kind == "below_reserve":
        data["robots"][0]["battery"] = 1
    else:
        data["robots"][0]["start"] = "B"
    with pytest.raises(ValueError):
        Scenario.from_dict(data)


def test_stations_must_be_distinct_boundary_vertices():
    data = mission()
    data["nodes"] = [{"id": "A", "x": 0, "y": 0}, {"id": "E", "x": 2, "y": 2},
                     {"id": "C", "x": 1, "y": 1}]
    data["edges"] = [{"source": "A", "target": "C"}, {"source": "C", "target": "E"}]
    data["robots"][0].update(start="C", station="C")
    with pytest.raises(ValueError, match="boundary"):
        Scenario.from_dict(data)
    data = mission()
    data["robots"][1].update(start="A", station="A")
    with pytest.raises(ValueError, match="station"):
        Scenario.from_dict(data)


@pytest.mark.parametrize("fraction", [0, 0.09, -1, 1.1, float("nan"), True])
def test_safety_reserve_cannot_be_disabled(fraction):
    data = mission()
    data["reserve_fraction"] = fraction
    with pytest.raises(ValueError):
        Scenario.from_dict(data)


@pytest.mark.parametrize("state", [State(([], "E"), (20, 20), (-1,), (False,)),
                                  State(("A", "E"), (float("nan"), 20), (-1,), (False,)),
                                  State(("A", "E"), (20, 20), (3,), (False,))])
def test_malformed_search_state_has_a_domain_error(state):
    with pytest.raises(ActionRejected) as caught:
        transition(Scenario.from_dict(mission(tasks=1)), state, {})
    assert caught.value.code == "invalid_state"


def test_weighted_distance_uses_shortest_cost_and_reports_disconnection():
    data = mission()
    data["edges"].append({"source": "A", "target": "C", "cost": 9})
    data["nodes"].append({"id": "Z", "x": 9, "y": 0})
    scenario = Scenario.from_dict(data)
    assert scenario.distance("A", "C") == 2
    assert scenario.distance("A", "A") == 0
    assert scenario.distance("A", "Z") == inf


def test_sequential_handoffs_then_delivery_and_return_complete_both_tasks():
    scenario = Scenario.from_dict(mission())
    sim = MissionSimulator(scenario)
    sim.step({"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "C", "R2": "C"},
              "transfers": [{"task": "T1", "from": "R1", "to": "R2"}]})
    assert sim.state.positions == ("C", "C")
    assert sim.state.owners == (1, -1)
    assert sim.state.handed == (True, False)
    assert sim.state.batteries == (18, 18)
    assert sim.timestep == 2
    sim.step({"moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "A", "R2": "E"}, "deliveries": ["T1"]})
    assert not sim.complete
    sim.step({"pickups": {"T2": "R2"}, "moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "C", "R2": "C"},
              "transfers": [{"task": "T2", "from": "R2", "to": "R1"}]})
    sim.step({"moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "A", "R2": "E"}, "deliveries": ["T2"]})
    assert sim.complete
    report = sim.report()
    assert report["success"] is True
    assert report["metrics"] == {"delivered_tasks": 2, "total_tasks": 2, "timesteps": 8,
                                  "total_energy": 16, "transfer_count": 2, "all_home": True}
    assert len(report["snapshots"]) == 9
    transfers = [e for e in report["events"] if e["type"] == "transfer"]
    assert len(transfers) == 2
    assert transfers[0]["timestep"] == 2
    assert {transfers[0]["from"], transfers[0]["to"]} == {"R1", "R2"}
    assert report["snapshots"][-1]["tasks"][0]["status"] == "delivered"
    assert all(r["cargo"] is None for r in report["snapshots"][-1]["robots"])


def test_rejection_keeps_state_and_tick_and_records_explanation():
    sim = MissionSimulator(Scenario.from_dict(mission()))
    approach(sim)
    before = sim.state
    snapshots = len(sim.snapshots)
    with pytest.raises(ActionRejected) as caught:
        sim.step({"moves": {"R1": "C", "R2": "C"}})
    assert caught.value.code == "transfer_required"
    assert caught.value.message
    assert sim.state == before
    assert sim.timestep == 1
    assert len(sim.snapshots) == snapshots
    assert sim.events[-1]["type"] == "rejected"
    assert sim.events[-1]["code"] == "transfer_required"


def test_two_robots_must_separate_after_transfer_or_transfer_again():
    sim = MissionSimulator(Scenario.from_dict(mission(tasks=1)))
    sim.step({"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "D"}})
    sim.step({"moves": {"R1": "C", "R2": "C"},
              "transfers": [{"task": "T1", "from": "R1", "to": "R2"}]})
    before = sim.state
    with pytest.raises(ActionRejected, match="transfer"):
        sim.step({})
    assert sim.state == before
    sim.step({"moves": {"R1": "B", "R2": "D"}})
    assert sim.state.positions == ("B", "D")


def test_idle_third_robot_cannot_disappear_to_allow_meeting():
    sim = MissionSimulator(Scenario.from_dict(mission(tasks=1, third=True)))
    sim.step({"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "D"}})
    before = sim.state
    with pytest.raises(ActionRejected) as caught:
        sim.step({"moves": {"R1": "C", "R2": "C"},
                  "transfers": [{"task": "T1", "from": "R1", "to": "R2"}]})
    assert caught.value.code == "vertex_capacity"
    assert sim.state == before
    assert sim.state.positions[2] == "C"


def test_wait_is_free_and_idle_robot_is_in_every_snapshot():
    sim = MissionSimulator(Scenario.from_dict(mission(third=True)))
    sim.step({"moves": {"R1": "A"}})
    assert sim.state.batteries == (20, 20, 20)
    assert sim.timestep == 1
    assert len(sim.snapshot()["robots"]) == 3
    assert sim.snapshot()["robots"][2]["position"] == "C"


def test_move_reserves_energy_for_own_station_with_individual_cost():
    data = mission(tasks=0)
    data["robots"][0].update(capacity=10, battery=5, move_cost=2)
    sim = MissionSimulator(Scenario.from_dict(data))
    sim.step({"moves": {"R1": "B"}})
    assert sim.state.batteries[0] == 3
    before = sim.state
    with pytest.raises(ActionRejected) as caught:
        sim.step({"moves": {"R1": "C"}})
    assert caught.value.code == "return_reserve"
    assert sim.state == before
    assert sim.snapshot()["robots"][0]["return_required"] == 2
    assert sim.snapshot()["robots"][0]["reserve"] == 1
    assert not sim.complete
    sim.step({"moves": {"R1": "A"}})
    assert sim.state.batteries[0] == 1
    assert sim.complete


def test_edge_cost_changes_energy_not_tick_duration():
    data = mission(tasks=0)
    data["edges"][0]["cost"] = 2.5
    data["robots"][0]["move_cost"] = 0.5
    sim = MissionSimulator(Scenario.from_dict(data))
    sim.step({"moves": {"R1": "B"}})
    assert sim.timestep == 1
    assert sim.state.batteries[0] == 18.75


def test_pickup_is_checked_before_movement_and_cannot_be_duplicated():
    sim = MissionSimulator(Scenario.from_dict(mission(tasks=1)))
    with pytest.raises(ActionRejected):
        sim.step({"pickups": {"T1": "R2"}, "moves": {"R2": "D"}})
    assert sim.state.owners == (-1,)
    sim.step({"pickups": {"T1": "R1"}})
    with pytest.raises(ActionRejected):
        sim.step({"pickups": {"T1": "R1"}})


def test_delivery_requires_previous_handoff_even_at_destination():
    data = mission(tasks=1)
    data["nodes"].append({"id": "F", "x": 4, "y": 1})
    data["edges"].append({"source": "E", "target": "F"})
    sim = MissionSimulator(Scenario.from_dict(data))
    sim.step({"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "F"}})
    sim.step({"moves": {"R1": "C"}})
    sim.step({"moves": {"R1": "D"}})
    sim.step({"moves": {"R1": "E"}})
    before = sim.state
    with pytest.raises(ActionRejected) as caught:
        sim.step({"deliveries": ["T1"]})
    assert caught.value.code == "handoff_required"
    assert sim.state == before


def test_transfers_require_real_ownership_and_same_arrival_vertex():
    sim = MissionSimulator(Scenario.from_dict(mission(tasks=1)))
    sim.step({"pickups": {"T1": "R1"}})
    with pytest.raises(ActionRejected):
        sim.step({"transfers": [{"task": "T1", "from": "R1", "to": "R2"}]})
    assert sim.state.owners == (0,)
    sim.step({"moves": {"R1": "B", "R2": "D"}})
    with pytest.raises(ActionRejected):
        sim.step({"moves": {"R1": "C", "R2": "C"}, "transfers": [
            {"task": "T1", "from": "R2", "to": "R1"}]})


@pytest.mark.parametrize("bad", ["duplicate_transfer", "self_transfer", "overload",
                                 "duplicate_delivery", "unknown_robot", "unknown_task"])
def test_malformed_actions_are_atomic(bad):
    sim = MissionSimulator(Scenario.from_dict(mission()))
    approach(sim)
    action = exchange()
    if bad == "duplicate_transfer":
        action["transfers"].append(dict(action["transfers"][0]))
    elif bad == "self_transfer":
        action["transfers"][0]["to"] = "R1"
    elif bad == "overload":
        action["transfers"] = action["transfers"][:1]
    elif bad == "duplicate_delivery":
        action["deliveries"] = ["T1", "T1"]
    elif bad == "unknown_robot":
        action["moves"]["ghost"] = "A"
    else:
        action["pickups"] = {"ghost": "R1"}
    before = sim.state
    with pytest.raises(ActionRejected):
        sim.step(action)
    assert sim.state == before
    assert sim.timestep == 1


def test_head_on_edge_swap_is_rejected():
    data = mission(tasks=0)
    data["edges"].append({"source": "A", "target": "E"})
    sim = MissionSimulator(Scenario.from_dict(data))
    with pytest.raises(ActionRejected) as caught:
        sim.step({"moves": {"R1": "E", "R2": "A"}})
    assert caught.value.code == "edge_swap"


def test_pure_transition_does_not_mutate_input_or_simulator():
    scenario = Scenario.from_dict(mission(tasks=1))
    initial = scenario.initial_state()
    action = {"pickups": {"T1": "R1"}, "moves": {"R1": "B"}}
    result = transition(scenario, initial, action)
    assert initial == scenario.initial_state()
    assert result.positions == ("B", "E")
    assert result.owners == (0,)
    assert action == {"pickups": {"T1": "R1"}, "moves": {"R1": "B"}}
