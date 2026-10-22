"""Exact small missions must include exchanges, energy and the trip home."""

from collections import Counter

from robotics.relay.model import Scenario
from robotics.relay.planner import RelayCoordinator
from robotics.relay.simulator import transition


def mission(length=3, robots=None, tasks=None):
    names = [chr(97 + i) for i in range(length)]
    return Scenario.from_dict({
        "name": "planner-test",
        "nodes": [{"id": name, "x": i, "y": 0} for i, name in enumerate(names)],
        "edges": [{"source": a, "target": b} for a, b in zip(names, names[1:])],
        "robots": robots or [robot("R1", names[0]), robot("R2", names[-1])],
        "tasks": tasks if tasks is not None else [
            {"id": "T1", "pickup": names[0], "dropoff": names[-1]},
        ],
        "reserve_fraction": 0.1,
    })


def robot(name, station, capacity=10, battery=None):
    return {"id": name, "start": station, "station": station,
            "capacity": capacity, "battery": capacity if battery is None else battery,
            "move_cost": 1}


def replay(scenario, result):
    state = scenario.initial_state()
    history = [state]
    for action in result.actions:
        state = transition(scenario, state, action)
        assert max(Counter(state.positions).values()) <= 2
        for i, spec in enumerate(scenario.robots):
            required = scenario.distance(state.positions[i], spec.station) * spec.move_cost
            assert state.batteries[i] + 1e-9 >= required + spec.capacity * 0.1
        history.append(state)
    return history


def test_shortest_plan_exchanges_delivers_and_returns_home():
    scenario = mission()
    result = RelayCoordinator(scenario).plan()
    assert result.success and result.optimal and result.status == "optimal"
    assert len(result.actions) == 2
    states = replay(scenario, result)
    assert states[-1].owners == (-2,)
    assert states[-1].handed == (True,)
    assert states[-1].positions == ("a", "c")
    assert any(action.get("transfers") for action in result.actions)
    assert scenario.initial_state() == states[0]


def test_waiting_is_allowed_without_energy_cost():
    scenario = mission(4)
    result = RelayCoordinator(scenario).plan()
    assert result.success and len(result.actions) == 4
    states = replay(scenario, result)
    waits = [(before, after, i) for before, after in zip(states, states[1:])
             for i in range(2) if before.positions[i] == after.positions[i]]
    assert waits
    assert all(before.batteries[i] == after.batteries[i] for before, after, i in waits)


def test_energy_constraints_require_two_handoffs_and_all_three_robots():
    scenario = mission(5, robots=[
        robot("R1", "a", 3), robot("R2", "c", 5), robot("R3", "e", 3),
    ])
    result = RelayCoordinator(scenario).plan()
    assert result.success and len(result.actions) == 4
    transfers = [item for action in result.actions for item in action.get("transfers", [])]
    assert {item["from"] for item in transfers} == {"R1", "R2"}
    assert {item["to"] for item in transfers} == {"R2", "R3"}
    final = replay(scenario, result)[-1]
    assert final.positions == ("a", "c", "e") and final.owners == (-2,)


def test_stationary_third_robot_remains_present_and_can_relay_the_cargo():
    scenario = mission(3, robots=[
        robot("R1", "a"), robot("R2", "c"), robot("R3", "b", 1, 0.1),
    ])
    result = RelayCoordinator(scenario).plan()
    assert result.success and len(result.actions) == 3
    states = replay(scenario, result)
    assert all(state.positions[2] == "b" and state.batteries[2] == 0.1 for state in states)
    transfers = [item for action in result.actions for item in action.get("transfers", [])]
    assert any(item["to"] == "R3" for item in transfers)
    assert any(item["from"] == "R3" for item in transfers)


def test_insufficient_energy_is_an_exhausted_search_not_an_invalid_plan():
    scenario = mission(3, robots=[robot("R1", "a", 1), robot("R2", "c", 1)])
    result = RelayCoordinator(scenario).plan()
    assert not result.success and not result.optimal and result.status == "no_plan"
    assert result.actions == [] and result.reason


def test_horizon_exhaustion_is_not_reported_as_proven_impossible():
    result = RelayCoordinator(mission()).plan(max_timesteps=1)
    assert not result.success and result.status == "horizon_limit"
    assert result.actions == []


def test_state_and_time_limits_are_reported_honestly():
    assert RelayCoordinator(mission()).plan(max_states=1).status == "state_limit"
    assert RelayCoordinator(mission()).plan(time_limit=0).status == "time_limit"


def test_completed_initial_state_needs_no_actions():
    result = RelayCoordinator(mission(tasks=[])).plan(max_timesteps=0)
    assert result.success and result.optimal and result.actions == []


def test_repeated_planning_is_deterministic_and_result_is_serializable():
    planner = RelayCoordinator(mission())
    first, second = planner.plan(), planner.plan()
    assert first.actions == second.actions
    payload = first.to_dict()
    assert payload["actions"] == first.actions and payload["optimal"] is True
    assert payload["expanded_states"] > 0 and payload["planning_time_ms"] >= 0


def test_weighted_edges_change_energy_but_still_take_one_timestep():
    data = mission(robots=[robot("R1", "a", 8), robot("R2", "c", 8)]).to_dict()
    for edge in data["edges"]:
        edge["cost"] = 3
    scenario = Scenario.from_dict(data)
    result = RelayCoordinator(scenario).plan()
    assert result.success and len(result.actions) == 2
    assert replay(scenario, result)[-1].batteries == (2, 2)


def test_a_robot_cannot_satisfy_mandatory_exchange_by_delivering_alone():
    scenario = mission(robots=[robot("R1", "a")])
    result = RelayCoordinator(scenario).plan()
    assert not result.success and result.status == "no_plan"
