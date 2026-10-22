"""Joint A* for small relay missions, with explicit and honest search limits."""

from __future__ import annotations

import heapq
import itertools
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from robotics.relay.model import EPSILON, Scenario, State
from robotics.relay.simulator import ActionRejected, _check_state, transition

@dataclass
class PlanResult:
    success: bool
    status: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    expanded_states: int = 0
    planning_time_ms: float = 0.0
    reason: str | None = None

    @property
    def optimal(self) -> bool:
        return self.success and self.status == "optimal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success, "status": self.status, "optimal": self.optimal,
            "actions": self.actions, "expanded_states": self.expanded_states,
            "planning_time_ms": self.planning_time_ms, "reason": self.reason,
        }


@dataclass(slots=True)
class _Node:
    state: State
    depth: int
    parent: int | None = None
    action: dict[str, Any] | None = None


class _TimeLimit(Exception):
    pass


class RelayCoordinator:
    """Minimise joint timesteps, including all deliveries and all trips home.

    Coordinates, cargo ownership, handoff flags and energy are search state.
    Pareto pruning only discards a state reached no sooner with no more energy.
    Edge costs affect energy; every move still takes exactly one timestep.
    """

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self._adj = scenario.adjacency
        self._ids = tuple(robot.id for robot in scenario.robots)
        self._hops = self._hop_distances()
        self._return_energy = tuple({
            node.id: scenario.distance(node.id, robot.station) * robot.move_cost
            + robot.capacity * scenario.reserve_fraction
            for node in scenario.nodes
        } for robot in scenario.robots)

    def plan(
        self, max_timesteps: int = 40, max_states: int = 150_000,
        time_limit: float = 10, *, initial_state: State | None = None,
    ) -> PlanResult:
        """Plan remaining ticks from a checkpoint, retaining cargo and energy."""
        if not isinstance(max_timesteps, int) or max_timesteps < 0:
            raise ValueError("max_timesteps must be a nonnegative integer")
        if not isinstance(max_states, int) or max_states < 1:
            raise ValueError("max_states must be a positive integer")
        if not math.isfinite(time_limit) or time_limit < 0:
            raise ValueError("time_limit must be finite and nonnegative")

        started = time.perf_counter()
        deadline = started + time_limit
        expanded = 0

        def result(status, actions=None, reason=None):
            return PlanResult(
                success=status == "optimal", status=status, actions=actions or [],
                expanded_states=expanded,
                planning_time_ms=(time.perf_counter() - started) * 1000,
                reason=reason,
            )

        initial = self.scenario.initial_state() if initial_state is None else initial_state
        _check_state(self.scenario, initial)
        for i, robot in enumerate(self.scenario.robots):
            if initial.batteries[i] > robot.battery + EPSILON:
                raise ActionRejected("invalid_state", f"Robot {robot.id} exceeds its initial energy")
            if initial.batteries[i] + EPSILON < self._return_energy[i][initial.positions[i]]:
                raise ActionRejected("invalid_state", f"Robot {robot.id} cannot return with its reserve")
        if any(initial.positions.count(position) > 2 for position in initial.positions):
            raise ActionRejected("invalid_state", "Checkpoint has more than two robots at a vertex")
        if self._finished(initial):
            return result("optimal")
        if time.perf_counter() >= deadline:
            return result("time_limit", reason="Planning time limit reached.")
        initial_bound = self._lower_bound(initial)
        if math.isinf(initial_bound):
            return result("no_plan", reason="A required destination is unreachable.")
        if initial_bound > max_timesteps:
            return result("horizon_limit", reason="No plan fits the timestep limit.")

        nodes = [_Node(initial, 0)]
        frontier = [(initial_bound, initial_bound, -sum(initial.batteries), 0)]
        active = {0}
        labels = {self._key(initial): [(0, initial.batteries, 0)]}
        horizon_cut = False

        try:
            while frontier:
                if time.perf_counter() >= deadline:
                    raise _TimeLimit
                _, _, _, node_id = heapq.heappop(frontier)
                if node_id not in active:
                    continue
                node = nodes[node_id]
                if self._finished(node.state):
                    return result("optimal", self._actions(nodes, node_id))
                if node.depth >= max_timesteps:
                    horizon_cut = True
                    continue
                expanded += 1

                for state, action in self._successors(node.state, deadline):
                    depth = node.depth + 1
                    bound = self._lower_bound(state)
                    if math.isinf(bound):
                        continue
                    if depth + bound > max_timesteps:
                        horizon_cut = True
                        continue
                    key = self._key(state)
                    previous = labels.get(key, [])
                    if any(g <= depth and self._enough(energy, state.batteries)
                           for g, energy, _ in previous):
                        continue
                    if len(nodes) >= max_states:
                        return result("state_limit", reason="Stored state limit reached.")
                    remaining = []
                    for g, energy, old_id in previous:
                        if depth <= g and self._enough(state.batteries, energy):
                            active.discard(old_id)
                        else:
                            remaining.append((g, energy, old_id))
                    child_id = len(nodes)
                    nodes.append(_Node(state, depth, node_id, action))
                    active.add(child_id)
                    remaining.append((depth, state.batteries, child_id))
                    labels[key] = remaining
                    heapq.heappush(frontier, (
                        depth + bound, bound, -sum(state.batteries), child_id,
                    ))
        except _TimeLimit:
            return result("time_limit", reason="Planning time limit reached.")

        if horizon_cut:
            return result("horizon_limit", reason="Search reached the timestep limit.")
        return result("no_plan", reason="All reachable energy-feasible states exhausted.")

    def _finished(self, state: State) -> bool:
        return all(owner == -2 for owner in state.owners) and all(
            state.positions[i] == robot.station
            and state.batteries[i] + EPSILON >= robot.capacity * self.scenario.reserve_fraction
            for i, robot in enumerate(self.scenario.robots)
        )

    @staticmethod
    def _key(state: State):
        return state.positions, state.owners, state.handed

    @staticmethod
    def _enough(left, right):
        return all(a + EPSILON >= b for a, b in zip(left, right))

    @staticmethod
    def _actions(nodes, node_id):
        actions = []
        while nodes[node_id].parent is not None:
            actions.append(nodes[node_id].action)
            node_id = nodes[node_id].parent
        return actions[::-1]

    def _hop_distances(self):
        distances = {}
        for origin in self._adj:
            found = {origin: 0}
            queue = deque([origin])
            while queue:
                cell = queue.popleft()
                for neighbor in self._adj[cell]:
                    if neighbor not in found:
                        found[neighbor] = found[cell] + 1
                        queue.append(neighbor)
            distances[origin] = found
        return distances

    def _distance(self, origin, destination):
        return self._hops[origin].get(destination, math.inf)

    def _lower_bound(self, state: State):
        # Ignore congestion, energy and the handoff requirement: each omitted
        # restriction can only make the estimated completion time smaller.
        bound = max((self._distance(state.positions[i], robot.station)
                     for i, robot in enumerate(self.scenario.robots)), default=0)
        for task, owner in zip(self.scenario.tasks, state.owners):
            if owner == -2:
                continue
            if owner == -1:
                approach = min((self._distance(pos, task.pickup)
                                for pos in state.positions), default=math.inf)
                remaining = approach + self._distance(task.pickup, task.dropoff)
            else:
                remaining = self._distance(state.positions[owner], task.dropoff)
            bound = max(bound, remaining)
        return bound

    def _pickups(self, state: State):
        free = [i for i in range(len(self._ids)) if i not in state.owners]

        def assign(offset, owners, pickups):
            if offset == len(free):
                yield owners, pickups
                return
            robot = free[offset]
            for index, task in enumerate(self.scenario.tasks):
                if owners[index] == -1 and state.positions[robot] == task.pickup:
                    chosen = list(owners)
                    chosen[index] = robot
                    yield from assign(offset + 1, tuple(chosen), {
                        **pickups, task.id: self._ids[robot],
                    })
            yield from assign(offset + 1, owners, pickups)

        yield from assign(0, state.owners, {})

    def _move_options(self, state: State, robot: int):
        origin = state.positions[robot]
        cost_per_move = self.scenario.robots[robot].move_cost
        options = []
        for destination in sorted({origin, *self._adj[origin]}):
            drain = 0 if destination == origin else self._adj[origin][destination] * cost_per_move
            if state.batteries[robot] - drain + EPSILON >= self._return_energy[robot][destination]:
                options.append(destination)
        return options

    def _successors(self, state: State, deadline: float):
        pickup_options = list(self._pickups(state))
        moves = [self._move_options(state, i) for i in range(len(self._ids))]
        for attempt, positions in enumerate(itertools.product(*moves)):
            if attempt % 64 == 0 and time.perf_counter() >= deadline:
                raise _TimeLimit
            groups = {}
            for i, position in enumerate(positions):
                groups.setdefault(position, []).append(i)
            if any(len(group) > 2 for group in groups.values()):
                continue
            if any(state.positions[i] != state.positions[j]
                   and positions[i] == state.positions[j] and positions[j] == state.positions[i]
                   for i in range(len(self._ids)) for j in range(i)):
                continue

            move_action = {self._ids[i]: pos for i, pos in enumerate(positions)
                           if pos != state.positions[i]}
            for owners, pickups in pickup_options:
                carried = {owner: task for task, owner in enumerate(owners) if owner >= 0}
                final_owners = list(owners)
                handed = list(state.handed)
                transfers = []
                valid = True
                for pair in groups.values():
                    if len(pair) != 2:
                        continue
                    left, right = pair
                    if (left in carried) == (right in carried):
                        valid = False
                        break
                    sender, recipient = (left, right) if left in carried else (right, left)
                    if recipient in state.owners:
                        valid = False
                        break
                    task_index = carried[sender]
                    final_owners[task_index] = recipient
                    handed[task_index] = True
                    transfers.append({
                        "task": self.scenario.tasks[task_index].id,
                        "from": self._ids[sender], "to": self._ids[recipient],
                    })
                if not valid:
                    continue
                deliverable = [task.id for i, task in enumerate(self.scenario.tasks)
                               if final_owners[i] >= 0 and handed[i]
                               and positions[final_owners[i]] == task.dropoff]
                # Prefer immediate delivery, but retain the other choices:
                # a held parcel may be needed for a later shared-vertex exchange.
                for mask in range((1 << len(deliverable)) - 1, -1, -1):
                    action = {"moves": move_action}
                    if pickups:
                        action["pickups"] = pickups
                    if transfers:
                        action["transfers"] = transfers
                    deliveries = [task for i, task in enumerate(deliverable) if mask & (1 << i)]
                    if deliveries:
                        action["deliveries"] = deliveries
                    try:
                        updated = transition(self.scenario, state, action)
                    except ActionRejected:
                        continue
                    if updated != state:
                        yield updated, action
