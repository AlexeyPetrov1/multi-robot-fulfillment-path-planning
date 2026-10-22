"""The rolling dispatcher keeps physical state and returns honest limits."""

import pytest
from dataclasses import replace

from robotics.relay.dispatch import RelayDispatcher
from robotics.relay.examples import example_scenarios
from robotics.relay.model import Scenario
from robotics.relay.simulator import ActionRejected, transition


def run(world, actions, state=None):
    state = state or world.initial_state()
    for action in actions:
        occupied = {owner for owner in state.owners if owner >= 0}
        used = set()
        for transfer in action.get("transfers", []):
            sender = world.robot_index[transfer["from"]]
            receiver = world.robot_index[transfer["to"]]
            assert receiver not in occupied
            assert not used.intersection((sender, receiver))
            used.update((sender, receiver))
        state = transition(world, state, action)
    return state


def test_dispatcher_solves_a_simple_handoff_without_claiming_optimality():
    world = Scenario.from_dict(example_scenarios()["simple_handoff"])
    result = RelayDispatcher(world).plan(max_timesteps=20)
    assert result.success and result.status == "feasible" and not result.optimal
    final = run(world, result.actions)
    assert final.owners == (-2,)
    assert final.positions == tuple(robot.station for robot in world.robots)


def test_dispatcher_resumes_actual_cargo_and_batteries_from_a_partial_state():
    world = Scenario.from_dict(example_scenarios()["simple_handoff"])
    first = {"pickups": {world.tasks[0].id: world.robots[0].id}}
    current = transition(world, world.initial_state(), first)
    result = RelayDispatcher(world).plan(max_timesteps=20, initial_state=current)
    assert result.success
    assert not any(action.get("pickups") for action in result.actions)
    assert run(world, result.actions, current).owners == (-2,)


@pytest.mark.parametrize("limit,expected", [(0, "horizon_limit"), (1, "horizon_limit")])
def test_horizon_is_honest_and_partial_actions_are_valid(limit, expected):
    world = Scenario.from_dict(example_scenarios()["simple_handoff"])
    result = RelayDispatcher(world).plan(max_timesteps=limit)
    assert not result.success and result.status == expected
    run(world, result.actions)


def test_exhausted_battery_is_a_dispatch_refusal_not_a_global_impossibility_claim():
    data = example_scenarios()["simple_handoff"]
    for robot in data["robots"]:
        robot["battery"] = robot["capacity"] * 0.1
    result = RelayDispatcher(Scenario.from_dict(data)).plan(max_timesteps=20)
    assert not result.success and result.status == "dispatch_limit"
    assert not result.actions


@pytest.mark.parametrize("kind", ["shape", "pending_handed", "battery_gain", "unsafe_return"])
def test_invalid_checkpoints_are_rejected_before_goal_or_dispatch(kind):
    data = example_scenarios()["simple_handoff"]
    data["robots"][0]["battery"] -= 1
    world = Scenario.from_dict(data)
    state = world.initial_state()
    if kind == "shape":
        state = replace(state, positions=())
    elif kind == "pending_handed":
        state = replace(state, handed=(True,))
    elif kind == "battery_gain":
        state = replace(state, batteries=(data["robots"][0]["battery"] + 0.5, state.batteries[1]))
    else:
        state = replace(state, positions=("M", state.positions[1]), batteries=(1, state.batteries[1]))
    with pytest.raises(ActionRejected):
        RelayDispatcher(world).plan(initial_state=state)


def test_delivery_can_finish_on_the_handoff_tick_at_the_destination():
    world = Scenario.from_dict({
        "name": "Destination handoff", "nodes": [{"id": "Z", "x": 0, "y": 0}, {"id": "A", "x": 1, "y": 0}],
        "edges": [{"source": "Z", "target": "A"}],
        "robots": [{"id": "collector", "start": "Z", "station": "Z", "capacity": 10, "battery": 10, "move_cost": 1},
                   {"id": "receiver", "start": "A", "station": "A", "capacity": 10, "battery": 1, "move_cost": 1}],
        "tasks": [{"id": "job", "pickup": "Z", "dropoff": "A"}],
    })
    result = RelayDispatcher(world).plan(max_timesteps=10)
    assert result.success
    final = run(world, result.actions)
    assert final.owners == (-2,) and final.positions == ("Z", "A")


@pytest.mark.parametrize("kwargs,status", [({"time_limit": 0}, "time_limit"), ({"max_states": 1}, "state_limit")])
def test_runtime_limits_keep_an_honest_valid_prefix(kwargs, status):
    world = Scenario.from_dict(example_scenarios()["simple_handoff"])
    result = RelayDispatcher(world).plan(**kwargs)
    assert not result.success and result.status == status
    run(world, result.actions)
