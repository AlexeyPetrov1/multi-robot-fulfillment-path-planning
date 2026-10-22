"""Compare A* with a raw-action BFS that shares only the transition rules."""

from collections import deque
from itertools import product
from random import Random

import pytest

from robotics.relay.model import Scenario
from robotics.relay.planner import RelayCoordinator
from robotics.relay.simulator import ActionRejected, transition


def raw_actions(scenario, state):
    ids = [robot.id for robot in scenario.robots]
    free = [i for i in range(len(ids)) if i not in state.owners]
    pickup_choices = [[None] + [q for q, task in enumerate(scenario.tasks)
                               if state.owners[q] == -1 and task.pickup == state.positions[i]]
                      for i in free]
    for selected in product(*pickup_choices):
        tasks = [q for q in selected if q is not None]
        if len(tasks) != len(set(tasks)):
            continue
        owners = list(state.owners)
        pickups = {}
        for robot, task in zip(free, selected):
            if task is not None:
                owners[task] = robot
                pickups[scenario.tasks[task].id] = ids[robot]

        destinations = [[cell] + list(scenario.adjacency[cell]) for cell in state.positions]
        for positions in product(*destinations):
            recipients = [[None] + ([i for i in range(len(ids))
                                    if i != owner and positions[i] == positions[owner]]
                                   if owner >= 0 else []) for owner in owners]
            for receiving in product(*recipients):
                transfers = [{"task": scenario.tasks[q].id,
                              "from": ids[owners[q]], "to": ids[robot]}
                             for q, robot in enumerate(receiving) if robot is not None]
                after = [robot if robot is not None else owners[q]
                         for q, robot in enumerate(receiving)]
                eligible = [q for q, owner in enumerate(after)
                            if owner >= 0 and (state.handed[q] or receiving[q] is not None)
                            and positions[owner] == scenario.tasks[q].dropoff]
                for mask in range(1 << len(eligible)):
                    yield {
                        "moves": {ids[i]: cell for i, cell in enumerate(positions)
                                  if cell != state.positions[i]},
                        "pickups": pickups, "transfers": transfers,
                        "deliveries": [scenario.tasks[q].id for j, q in enumerate(eligible)
                                       if mask & (1 << j)],
                    }


def minimum_ticks(scenario, horizon):
    """No heuristic, Pareto pruning, reservation table or planner helper."""
    initial = scenario.initial_state()
    queue = deque([(initial, 0)])
    seen = {initial}
    while queue:
        state, depth = queue.popleft()
        if all(owner == -2 for owner in state.owners) and all(
            state.positions[i] == robot.station
            and state.batteries[i] + 1e-9 >= robot.capacity * scenario.reserve_fraction
            for i, robot in enumerate(scenario.robots)
        ):
            return depth
        if depth == horizon:
            continue
        for action in raw_actions(scenario, state):
            try:
                updated = transition(scenario, state, action)
            except ActionRejected:
                continue
            if updated not in seen:
                seen.add(updated)
                queue.append((updated, depth + 1))
    return None


def cases():
    rng = Random(20261022)
    for index in range(12):
        edges = [{"source": "a", "target": "b", "cost": rng.choice([0.5, 1, 2])},
                 {"source": "b", "target": "c", "cost": rng.choice([0.5, 1, 2])}]
        if index % 3 == 0:
            edges.append({"source": "a", "target": "c", "cost": rng.choice([0.5, 2, 3])})
        robots = []
        for name, station in (("R1", "a"), ("R2", "c")):
            capacity = rng.choice([3, 6, 10])
            robots.append({"id": name, "start": station, "station": station,
                           "capacity": capacity, "battery": capacity,
                           "move_cost": rng.choice([0.5, 1, 2])})
        tasks = [{"id": "T1", "pickup": "a", "dropoff": rng.choice(["b", "c"])}]
        if index % 4 == 0:
            tasks.append({"id": "T2", "pickup": "c", "dropoff": "a"})
        yield {"name": f"reference-{index}", "reserve_fraction": 0.1,
               "nodes": [{"id": name, "x": i, "y": 0} for i, name in enumerate("abc")],
               "edges": edges, "robots": robots, "tasks": tasks}


@pytest.mark.parametrize("data", list(cases()), ids=lambda data: data["name"])
def test_astar_matches_independent_raw_action_bfs(data):
    scenario = Scenario.from_dict(data)
    expected = minimum_ticks(scenario, horizon=5)
    result = RelayCoordinator(scenario).plan(max_timesteps=5, time_limit=10)
    assert result.success == (expected is not None), (data, result.to_dict())
    if expected is not None:
        assert result.optimal and len(result.actions) == expected
    else:
        assert result.status in ("no_plan", "horizon_limit")
