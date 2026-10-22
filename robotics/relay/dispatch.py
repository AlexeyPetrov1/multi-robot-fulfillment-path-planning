"""Rolling geographic relay: assign from current state and move one joint tick."""

from __future__ import annotations

import heapq
import math
import time
from collections import Counter

from robotics.relay.model import EPSILON, Scenario, State
from robotics.relay.planner import PlanResult
from robotics.relay.simulator import ActionRejected, _check_state, transition


class _Limit(Exception):
    def __init__(self, status):
        self.status = status


class RelayDispatcher:
    """A bounded heuristic, not an optimal or complete solver.

    Stations nearest the loading area collect; the other robots deliver.
    Empty couriers reserve different balanced handoff points. Assignment and
    routing use the actual position, cargo and remaining battery every tick.
    """

    def __init__(self, scenario: Scenario):
        self.world = scenario
        self.ids = tuple(robot.id for robot in scenario.robots)
        self.candidates = {}

    def plan(self, max_timesteps=1000, max_states=500000, time_limit=30,
             *, initial_state: State | None = None):
        if type(max_timesteps) is not int or max_timesteps < 0:
            raise ValueError("max_timesteps must be a nonnegative integer")
        if type(max_states) is not int or max_states < 1:
            raise ValueError("max_states must be positive")
        if not math.isfinite(time_limit) or time_limit < 0:
            raise ValueError("time_limit must be finite and nonnegative")
        started = time.perf_counter()
        self.deadline, self.max_states, self.expanded = started + time_limit, max_states, 0
        state = self.world.initial_state() if initial_state is None else initial_state
        _check_state(self.world, state)
        for ri, robot in enumerate(self.world.robots):
            if state.batteries[ri] > robot.battery + EPSILON or not self.affords(
                    state, ri, self.distance(state.positions[ri], robot.station)):
                raise ActionRejected("invalid_state", f"Robot {robot.id} has an unsafe checkpoint energy")
        if any(state.positions.count(position) > 2 for position in state.positions):
            raise ActionRejected("invalid_state", "Checkpoint has more than two robots at a vertex")
        actions, jobs, delivering = [], {}, {}
        usage = Counter()
        for ti, owner in enumerate(state.owners):
            if owner >= 0:
                if state.handed[ti]:
                    delivering[owner] = ti
                else:
                    jobs[ti] = {"collector": owner, "receiver": None, "meeting": None}
        ordered = sorted(range(len(self.ids)), key=lambda ri: (
            sum(self.distance(self.world.robots[ri].station, task.pickup)
                - self.distance(self.world.robots[ri].station, task.dropoff)
                for task in self.world.tasks), self.ids[ri]))
        split = max(1, len(ordered) // 2)
        collectors, couriers = ordered[:split], ordered[split:]

        def finish(status, reason=None):
            return PlanResult(status == "feasible", status, actions, self.expanded,
                              (time.perf_counter() - started) * 1000, reason)

        try:
            for _ in range(max_timesteps + 1):
                if self.complete(state):
                    return finish("feasible")
                self.check_limit()
                if len(actions) == max_timesteps:
                    return finish("horizon_limit", "The rolling dispatch reached its timestep limit.")
                busy = set(delivering)
                for job in jobs.values():
                    busy.add(job["collector"])
                    if job["receiver"] is not None:
                        busy.add(job["receiver"])
                pending = [ti for ti, owner in enumerate(state.owners) if owner == -1 and ti not in jobs]
                while pending:
                    options = [(self.distance(state.positions[ri], self.world.tasks[ti].pickup), ti, ri)
                               for ri in collectors if ri not in busy for ti in pending
                               if any(self.affords(state, ri,
                                      self.distance(state.positions[ri], self.world.tasks[ti].pickup)
                                      + self.distance(self.world.tasks[ti].pickup, node)
                                      + self.distance(node, self.world.robots[ri].station))
                                      for node in self.meeting_candidates(ti))]
                    if not options:
                        break
                    _, ti, ri = min(options)
                    jobs[ti] = {"collector": ri, "receiver": None, "meeting": None}
                    busy.add(ri)
                    pending.remove(ti)
                for receiver in couriers:
                    if receiver in busy or receiver in state.owners:
                        continue
                    options = []
                    occupied_meetings = [j["meeting"] for j in jobs.values() if j["meeting"]]
                    for ti, job in jobs.items():
                        collector = job["collector"]
                        if job["receiver"] is not None or collector == receiver:
                            continue
                        task = self.world.tasks[ti]
                        pickup = task.pickup if state.owners[ti] == -1 else state.positions[collector]
                        approach = self.distance(state.positions[collector], pickup)
                        for node in self.meeting_candidates(ti):
                            if any(position == node for ri, position in enumerate(state.positions)
                                   if ri not in (collector, receiver)):
                                continue
                            if any(self.distance(node, other) < 4 for other in occupied_meetings):
                                continue
                            first = approach + self.distance(pickup, node)
                            second = self.distance(state.positions[receiver], node)
                            if (self.affords(state, collector, first + self.distance(node, self.world.robots[collector].station))
                                    and self.affords(state, receiver, second + self.distance(node, task.dropoff)
                                                     + self.distance(task.dropoff, self.world.robots[receiver].station))):
                                options.append(((max(first, second), usage[node], ti, node), ti, node))
                    if options:
                        _, ti, node = min(options)
                        jobs[ti].update(receiver=receiver, meeting=node)
                        usage[node] += 1
                        busy.add(receiver)
                targets, pickups = {}, {}
                for ti, job in jobs.items():
                    ri, receiver = job["collector"], job["receiver"]
                    task = self.world.tasks[ti]
                    loaded = state.owners[ti] == ri
                    if not loaded and state.positions[ri] == task.pickup:
                        pickups[task.id] = self.ids[ri]
                        loaded = True
                    targets[ri] = job["meeting"] if loaded and receiver is not None else task.pickup
                    if receiver is not None:
                        targets[receiver] = job["meeting"]
                targets.update({ri: self.world.tasks[ti].dropoff for ri, ti in delivering.items()})
                if all(owner == -2 for owner in state.owners):
                    targets = {ri: spec.station for ri, spec in enumerate(self.world.robots)}
                moves, next_positions = {}, list(state.positions)
                reserved = {}
                priority = sorted(range(len(self.ids)), key=lambda ri: (ri not in delivering, ri))
                for ri in priority:
                    goal = targets.get(ri, state.positions[ri])
                    allowed = set()
                    for job in jobs.values():
                        if job["receiver"] is None or ri not in (job["collector"], job["receiver"]):
                            continue
                        pair, node = {job["collector"], job["receiver"]}, job["meeting"]
                        occupants = {i for i, position in enumerate(state.positions) if position == node}
                        if occupants <= pair and reserved.get(node, set()) <= pair:
                            allowed.add(node)
                    blocked = {position for index, position in enumerate(state.positions) if index != ri}
                    blocked.update(reserved)
                    blocked.difference_update(allowed)
                    destination = self.step(state, ri, goal, blocked)
                    if destination != state.positions[ri]:
                        moves[self.ids[ri]] = destination
                    next_positions[ri] = destination
                    reserved.setdefault(destination, set()).add(ri)
                transfers = []
                for ti, job in jobs.items():
                    ri, receiver, node = job["collector"], job["receiver"], job["meeting"]
                    if (receiver is not None and next_positions[ri] == next_positions[receiver] == node
                            and (state.owners[ti] == ri or self.world.tasks[ti].id in pickups)):
                        transfers.append({"task": self.world.tasks[ti].id,
                                          "from": self.ids[ri], "to": self.ids[receiver]})
                deliveries = [self.world.tasks[ti].id for ri, ti in delivering.items()
                              if next_positions[ri] == self.world.tasks[ti].dropoff]
                deliveries.extend(transfer["task"] for transfer in transfers
                                  if next_positions[self.world.robot_index[transfer["to"]]]
                                  == self.world.tasks[self.world.task_index[transfer["task"]]].dropoff)
                action = {"moves": moves}
                for key, value in (("pickups", pickups), ("transfers", transfers), ("deliveries", deliveries)):
                    if value:
                        action[key] = value
                if not moves and not pickups and not transfers and not deliveries:
                    return finish("dispatch_limit", "No safe progress was found by the rolling policy.")
                try:
                    state = transition(self.world, state, action)
                except ActionRejected as error:
                    return finish("dispatch_limit", f"Joint move refused: {error.code}: {error.message}")
                actions.append(action)
                for transfer in transfers:
                    ti = self.world.task_index[transfer["task"]]
                    delivering[self.world.robot_index[transfer["to"]]] = ti
                    del jobs[ti]
                for task in deliveries:
                    ti = self.world.task_index[task]
                    delivering = {ri: other for ri, other in delivering.items() if other != ti}
        except _Limit as limit:
            return finish(limit.status, "The rolling dispatch reached its search limit.")

    def distance(self, left, right):
        return self.world.distance(left, right)

    def affords(self, state, ri, moves):
        robot = self.world.robots[ri]
        return state.batteries[ri] + EPSILON >= moves * robot.move_cost + robot.capacity * self.world.reserve_fraction

    def meeting_candidates(self, ti):
        if ti not in self.candidates:
            task = self.world.tasks[ti]
            length = self.distance(task.pickup, task.dropoff)
            choices = [node.id for node in self.world.nodes
                       if self.distance(task.pickup, node.id) + self.distance(node.id, task.dropoff) <= length + EPSILON]
            imbalance = min((abs(self.distance(task.pickup, n) - self.distance(n, task.dropoff)) for n in choices), default=math.inf)
            self.candidates[ti] = [n for n in choices if abs(self.distance(task.pickup, n) - self.distance(n, task.dropoff)) <= imbalance + EPSILON]
        return self.candidates[ti]

    def step(self, state, ri, goal, blocked):
        start = state.positions[ri]
        if start == goal:
            return start
        queue = [(self.distance(goal, start), self.distance(goal, start), 0, start, start)]
        best = {start: 0}
        while queue:
            self.check_limit()
            _, _, cost, node, first = heapq.heappop(queue)
            self.expanded += 1
            if node == goal:
                return first
            if cost > best[node] + EPSILON:
                continue
            for neighbor, weight in self.world.adjacency[node].items():
                new_cost = cost + weight
                if neighbor in blocked or not self.affords(state, ri, new_cost + self.distance(neighbor, self.world.robots[ri].station)):
                    continue
                if new_cost + EPSILON < best.get(neighbor, math.inf):
                    best[neighbor] = new_cost
                    heuristic = self.distance(goal, neighbor)
                    heapq.heappush(queue, (new_cost + heuristic, heuristic, new_cost,
                                          neighbor, neighbor if node == start else first))
        return start

    def check_limit(self):
        if time.perf_counter() >= self.deadline:
            raise _Limit("time_limit")
        if self.expanded >= self.max_states:
            raise _Limit("state_limit")

    def complete(self, state):
        return all(owner == -2 for owner in state.owners) and all(
            state.positions[ri] == robot.station
            and state.batteries[ri] + EPSILON >= robot.capacity * self.world.reserve_fraction
            for ri, robot in enumerate(self.world.robots))
