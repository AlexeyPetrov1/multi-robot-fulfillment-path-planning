"""A continuous warehouse shift needs relay under any solo assignment."""

import json
from collections import Counter
from math import floor
from pathlib import Path

import pytest

from robotics.relay.dispatch import RelayDispatcher
from robotics.relay.model import Scenario, State
from robotics.services.relay_service import replay_mission


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def prepared():
    data = json.loads((ROOT / "scenarios/grid16_team4_25.json").read_text(encoding="utf-8"))
    actions = json.loads((ROOT / "scenarios/plans/grid16_team4_25.actions.json").read_text(encoding="utf-8"))
    return data, actions, Scenario.from_dict(data), replay_mission(data, actions)


def test_real_named_loading_docks_and_twenty_five_different_orders(prepared):
    data, _, world, _ = prepared
    assert len(world.nodes) == 256 and len(world.edges) == 480
    positions = {node.id: (node.x, node.y) for node in world.nodes}
    actual = {frozenset((positions[edge.source], positions[edge.target])) for edge in world.edges}
    expected = {frozenset(((x, y), (x + dx, y + dy)))
                for x in range(16) for y in range(16) for dx, dy in ((1, 0), (0, 1))
                if x + dx < 16 and y + dy < 16}
    assert actual == expected and all(edge.cost == 1 for edge in world.edges)
    assert len(world.robots) == 4 and len(world.tasks) == 25
    assert len({(task.pickup, task.dropoff) for task in world.tasks}) == 25
    assert len({task.pickup for task in world.tasks}) == len({task.dropoff for task in world.tasks}) == 5
    assert all(task.label and "→" in task.label for task in world.tasks)
    assert all(world.nodes[world.node_index[task.pickup]].label for task in world.tasks)
    assert all(world.nodes[world.node_index[task.dropoff]].label for task in world.tasks)
    assert data["energy_scope"] == "global_no_handoff_capacity"


def test_global_lower_bound_does_not_depend_on_assignment_order_or_transfer_rule(prepared):
    data, _, world, _ = prepared
    for task in world.tasks:
        assert world.distance(task.pickup, task.dropoff) == 22
        for following in world.tasks:
            assert world.distance(task.dropoff, following.pickup) == 22
    for robot in world.robots:
        for first in world.tasks:
            for last in world.tasks:
                assert (world.distance(robot.station, first.pickup)
                        + world.distance(last.dropoff, robot.station)) >= 22
    budgets = [floor((robot.battery - robot.capacity * 0.1) / robot.move_cost + 1e-8)
               for robot in world.robots]
    assert budgets == [306, 306, 306, 306]
    assert max(budgets) < 7 * (22 + 22)
    assert sum(budget // 44 for budget in budgets) == 24 < len(world.tasks)
    assert data["no_handoff_bound"]["maximum_team_jobs"] == 24


def test_complete_continuous_plan_has_only_empty_receiver_one_way_handoffs(prepared):
    data, actions, world, report = prepared
    assert report["success"] and report["status"] == "completed"
    assert not report.get("optimal", False)
    assert all("charges" not in action for action in actions)
    assert all("charge_rate" not in robot for robot in data["robots"])
    transfers = [event for event in report["events"] if event["type"] == "transfer"]
    assert Counter(event["task"] for event in transfers) == {task.id: 1 for task in world.tasks}
    meetings = set()
    for action, before, after in zip(actions, report["snapshots"], report["snapshots"][1:]):
        old = {robot["id"]: robot for robot in before["robots"]}
        new = {robot["id"]: robot for robot in after["robots"]}
        used = set()
        for transfer in action.get("transfers", []):
            sender, receiver = transfer["from"], transfer["to"]
            assert old[receiver]["cargo"] is None
            assert not used.intersection((sender, receiver))
            used.update((sender, receiver))
            assert new[sender]["position"] == new[receiver]["position"]
            meetings.add(new[sender]["position"])
    assert len(meetings) >= 4
    assert {event[key] for event in transfers for key in ("from", "to")} == {robot.id for robot in world.robots}


def test_energy_never_resets_and_robots_return_only_at_shift_end(prepared):
    _, actions, world, report = prepared
    spent = Counter()
    departed = set()
    for action, before, after in zip(actions, report["snapshots"], report["snapshots"][1:]):
        for spec, old, new in zip(world.robots, before["robots"], after["robots"]):
            drain = (world.adjacency[old["position"]][new["position"]] * spec.move_cost
                     if old["position"] != new["position"] else 0)
            assert new["battery"] == pytest.approx(old["battery"] - drain, abs=1e-8)
            assert new["battery"] + 1e-8 >= new["return_required"] + new["reserve"]
            spent[spec.id] += drain
            if new["position"] != spec.station:
                departed.add(spec.id)
            elif spec.id in departed:
                assert all(task["status"] == "delivered" for task in before["tasks"])
    assert min(spent.values()) > 150
    assert report["metrics"]["total_energy"] == pytest.approx(sum(spent.values()))
    assert all(robot["position"] == robot["station"] and robot["battery"] >= robot["reserve"]
               for robot in report["snapshots"][-1]["robots"])
    assert all(task["status"] == "delivered" and task["handed"] for task in report["snapshots"][-1]["tasks"])
    assert sum(len(action.get("moves", {})) == 4 for action in actions) >= 80


def test_dispatcher_reproduces_checked_actions_and_resumes_with_real_state(prepared):
    from scripts.build_grid16_team4_25 import build, global_energy_bound
    from robotics.relay.simulator import transition

    data, actions, world, _ = prepared
    assert build() == (data, actions)
    result = RelayDispatcher(world).plan(max_timesteps=1000, max_states=500000, time_limit=30)
    assert result.success and result.status == "feasible" and not result.optimal
    assert result.actions == actions
    assert data["no_handoff_bound"] == global_energy_bound(data)
    state = world.initial_state()
    for action in actions[:24]:
        state = transition(world, state, action)
    suffix = RelayDispatcher(world).plan(max_timesteps=1000, max_states=500000,
                                         time_limit=30, initial_state=state)
    assert suffix.success
    for action in suffix.actions:
        state = transition(world, state, action)
    assert all(owner == -2 for owner in state.owners)
    assert state.positions == tuple(robot.station for robot in world.robots)


@pytest.mark.parametrize("positions,batteries,owner", [
    (("v7_8", "v0_4", "v15_11", "v10_12"), (83, 81.6, 105, 140), -1),
    (("v7_8", "v5_7", "v15_11", "v8_7"), (83, 72, 105, 126), 1),
    (("v7_8", "v6_7", "v15_11", "v8_7"), (83, 70.8, 105, 126), 1),
])
def test_last_order_uses_the_closest_free_collector_and_an_unoccupied_meeting(prepared, positions, batteries, owner):
    _, _, world, _ = prepared
    state = State(positions, batteries, (-2,) * 24 + (owner,), (True,) * 24 + (False,))
    result = RelayDispatcher(world).plan(initial_state=state)
    assert result.success
    from robotics.relay.simulator import transition
    for action in result.actions:
        state = transition(world, state, action)
    assert all(task == -2 for task in state.owners)
