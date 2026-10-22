"""Atomic mission execution. Planning and replay use the same transition rules."""

from __future__ import annotations

from math import isfinite

from robotics.relay.model import EPSILON, Scenario, State


class ActionRejected(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _reject(code, message, **details):
    raise ActionRejected(code, message, details)


def _index(mapping, key, kind):
    if not isinstance(key, str) or key not in mapping:
        _reject(f"unknown_{kind}", f"Unknown {kind}: {key!r}")
    return mapping[key]


def _action_parts(action):
    if not isinstance(action, dict) or set(action) - {"moves", "pickups", "transfers", "deliveries"}:
        _reject("invalid_action", "Action must contain only moves, pickups, transfers and deliveries")
    moves, pickups = action.get("moves", {}), action.get("pickups", {})
    transfers, deliveries = action.get("transfers", []), action.get("deliveries", [])
    if not isinstance(moves, dict) or not isinstance(pickups, dict):
        _reject("invalid_action", "Moves and pickups must be objects")
    if not isinstance(transfers, list) or not isinstance(deliveries, list):
        _reject("invalid_action", "Transfers and deliveries must be lists")
    if any(not isinstance(t, dict) or set(t) != {"task", "from", "to"} for t in transfers):
        _reject("invalid_action", "Each transfer needs task, from and to")
    if any(not isinstance(t, str) for t in deliveries) or len(set(deliveries)) != len(deliveries):
        _reject("duplicate_delivery", "Deliveries must contain distinct task ids")
    return moves, pickups, transfers, deliveries


def _check_state(scenario, state):
    if (not isinstance(state, State)
            or any(not isinstance(values, tuple) for values in (
                state.positions, state.batteries, state.owners, state.handed))
            or len(state.positions) != len(scenario.robots)
            or len(state.batteries) != len(scenario.robots)
            or len(state.owners) != len(scenario.tasks)
            or len(state.handed) != len(scenario.tasks)):
        _reject("invalid_state", "State dimensions do not match the scenario")
    for i, robot in enumerate(scenario.robots):
        if not isinstance(state.positions[i], str) or state.positions[i] not in scenario.adjacency:
            _reject("invalid_state", f"Robot {robot.id} is outside the graph")
        battery = state.batteries[i]
        if isinstance(battery, bool) or not isinstance(battery, (int, float)) or not isfinite(battery):
            _reject("invalid_state", f"Robot {robot.id} battery must be finite")
        if battery < -EPSILON or battery > robot.capacity + EPSILON:
            _reject("invalid_state", f"Robot {robot.id} battery is outside its capacity")
    for owner, handed in zip(state.owners, state.handed):
        if type(owner) is not int or not -2 <= owner < len(scenario.robots) or type(handed) is not bool:
            _reject("invalid_state", "Invalid task owner or handoff flag")
        if owner == -2 and not handed:
            _reject("invalid_state", "Delivered tasks must have a handoff")
        if owner == -1 and handed:
            _reject("invalid_state", "Pending tasks cannot have a handoff")
    _check_cargo(state.owners)


def _check_cargo(owners):
    loaded = [owner for owner in owners if owner >= 0]
    if len(loaded) != len(set(loaded)):
        _reject("cargo_capacity", "A robot can carry only one task at a time")


def transition(scenario: Scenario, state: State, action: dict) -> State:
    """Validate an atomic tick: pickup, move, arrival handoff, then delivery.

    A handoff snapshot shows both robots stopped at the same vertex. They can
    depart next tick; no extra waiting phase is required. A receiver must be
    empty before this tick and cannot pick up another task during it.
    """
    _check_state(scenario, state)
    moves, pickups, transfers, deliveries = _action_parts(action)
    owners, handed = list(state.owners), list(state.handed)
    positions, batteries = list(state.positions), list(state.batteries)

    # Pickups happen before movement and cannot borrow another cargo slot.
    for task_id, robot_id in pickups.items():
        ti = _index(scenario.task_index, task_id, "task")
        ri = _index(scenario.robot_index, robot_id, "robot")
        if owners[ti] != -1:
            _reject("already_picked", f"Task {task_id} has already been picked up")
        if ri in owners:
            _reject("cargo_capacity", f"Robot {robot_id} is already carrying a task")
        if state.positions[ri] != scenario.tasks[ti].pickup:
            _reject("pickup_location", f"Robot {robot_id} is not at the pickup for {task_id}")
        owners[ti] = ri

    for robot_id, destination in moves.items():
        ri = _index(scenario.robot_index, robot_id, "robot")
        if not isinstance(destination, str) or destination not in scenario.adjacency:
            _reject("unknown_node", f"Unknown destination: {destination!r}")
        source = state.positions[ri]
        if destination != source:
            if destination not in scenario.adjacency[source]:
                _reject("invalid_move", f"Robot {robot_id}: no edge {source} -> {destination}")
            batteries[ri] -= scenario.adjacency[source][destination] * scenario.robots[ri].move_cost
        positions[ri] = destination

    # Safety includes a weighted shortest return and the robot's own reserve.
    for ri, robot in enumerate(scenario.robots):
        home = scenario.distance(positions[ri], robot.station) * robot.move_cost
        reserve = robot.capacity * scenario.reserve_fraction
        if batteries[ri] + EPSILON < home + reserve:
            _reject("return_reserve", f"Robot {robot.id}: move leaves insufficient energy "
                    f"to return to {robot.station} with its reserve", robot=robot.id,
                    battery=batteries[ri], return_required=home, reserve=reserve)
    for a in range(len(positions)):
        for b in range(a + 1, len(positions)):
            if (positions[a] != state.positions[a] and positions[b] != state.positions[b]
                    and positions[a] == state.positions[b] and positions[b] == state.positions[a]):
                _reject("edge_swap", f"Robots {scenario.robots[a].id} and "
                        f"{scenario.robots[b].id} cannot swap across an edge")

    transferred, meetings, participants = set(), set(), set()
    before_transfers = owners[:]
    for transfer in transfers:
        task_id, sender_id, receiver_id = transfer["task"], transfer["from"], transfer["to"]
        ti = _index(scenario.task_index, task_id, "task")
        sender = _index(scenario.robot_index, sender_id, "robot")
        receiver = _index(scenario.robot_index, receiver_id, "robot")
        if ti in transferred:
            _reject("duplicate_transfer", f"Task {task_id} can be transferred only once per tick")
        if sender == receiver:
            _reject("self_transfer", f"Task {task_id} needs two different robots for a transfer")
        if sender in participants or receiver in participants:
            _reject("transfer_busy", "A robot can participate in only one transfer per tick")
        if before_transfers[ti] != sender:
            _reject("transfer_owner", f"Robot {sender_id} does not own task {task_id}")
        if receiver in state.owners or receiver in before_transfers:
            _reject("receiver_loaded", f"Robot {receiver_id} must be empty before a transfer")
        if positions[sender] != positions[receiver]:
            _reject("transfer_location", f"Robots {sender_id} and {receiver_id} must meet "
                    "at the same vertex for a transfer")
        owners[ti], handed[ti] = receiver, True
        transferred.add(ti)
        participants.update((sender, receiver))
        meetings.add(frozenset((sender, receiver)))
    _check_cargo(owners)

    occupancy = {}
    for ri, position in enumerate(positions):
        occupancy.setdefault(position, []).append(ri)
    for position, occupants in occupancy.items():
        if len(occupants) > 2:
            _reject("vertex_capacity", f"Vertex {position} cannot contain more than two robots",
                    vertex=position, robots=[scenario.robots[i].id for i in occupants])
        if len(occupants) == 2 and frozenset(occupants) not in meetings:
            _reject("transfer_required", f"Two robots may share vertex {position} only "
                    "during a valid transfer in this tick", vertex=position)

    for task_id in deliveries:
        ti = _index(scenario.task_index, task_id, "task")
        owner = owners[ti]
        if owner < 0:
            _reject("delivery_owner", f"Task {task_id} is not being carried")
        if positions[owner] != scenario.tasks[ti].dropoff:
            _reject("delivery_location", f"Task {task_id} is not at its destination")
        if not handed[ti]:
            _reject("handoff_required", f"Task {task_id} needs at least one handoff before delivery")
        owners[ti] = -2
    return State(tuple(positions), tuple(round(max(0, b), 9) for b in batteries),
                 tuple(owners), tuple(handed))


class MissionSimulator:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.state = scenario.initial_state()
        self.timestep = 0
        self.events = []
        self.snapshots = [self.snapshot()]

    @property
    def complete(self):
        return (all(owner == -2 for owner in self.state.owners)
                and all(self.state.positions[i] == r.station
                        and self.state.batteries[i] + EPSILON >= r.capacity * self.scenario.reserve_fraction
                        for i, r in enumerate(self.scenario.robots)))

    def step(self, action):
        try:
            updated = transition(self.scenario, self.state, action)
        except ActionRejected as error:
            self.events.append({"timestep": self.timestep, "type": "rejected",
                                "code": error.code, "message": error.message, **error.details})
            raise
        previous = self.state
        self.state = updated
        self.timestep += 1
        self._record_events(previous, action)
        self.snapshots.append(self.snapshot())
        return self.state

    def _record_events(self, previous, action):
        def record(kind, message, **details):
            self.events.append({"timestep": self.timestep, "type": kind,
                                "message": message, **details})
        for task_id, robot_id in action.get("pickups", {}).items():
            record("pickup", f"{robot_id} picked up {task_id}", task=task_id, robot=robot_id)
        for i, robot in enumerate(self.scenario.robots):
            source, destination = previous.positions[i], self.state.positions[i]
            record("wait" if source == destination else "move",
                   f"{robot.id}: {source} -> {destination}", robot=robot.id,
                   **{"from": source, "to": destination,
                       "energy": round(previous.batteries[i] - self.state.batteries[i], 9)})
        for transfer in action.get("transfers", []):
            record("transfer", f"{transfer['from']} передал груз {transfer['task']} "
                   f"роботу {transfer['to']}", **transfer)
        for task_id in action.get("deliveries", []):
            record("delivery", f"{task_id} delivered", task=task_id)

    def snapshot(self):
        robots = []
        for i, robot in enumerate(self.scenario.robots):
            cargo = next((self.scenario.tasks[j].id for j, owner in enumerate(self.state.owners)
                          if owner == i), None)
            robots.append({"id": robot.id, "position": self.state.positions[i],
                           "station": robot.station, "battery": self.state.batteries[i],
                           "capacity": robot.capacity, "move_cost": robot.move_cost, "cargo": cargo,
                           "return_required": self.scenario.distance(self.state.positions[i], robot.station)
                           * robot.move_cost, "reserve": robot.capacity * self.scenario.reserve_fraction,
                           "status": "carrying" if cargo else "home"
                           if self.state.positions[i] == robot.station else "idle"})
        tasks = [{"id": task.id, "pickup": task.pickup, "dropoff": task.dropoff,
                  **({"label": task.label} if task.label is not None else {}),
                  "owner": self.scenario.robots[owner].id if owner >= 0 else None,
                  "status": "delivered" if owner == -2 else "pending" if owner == -1 else "carried",
                  "handed": self.state.handed[i]}
                 for i, (task, owner) in enumerate(zip(self.scenario.tasks, self.state.owners))]
        return {"timestep": self.timestep, "robots": robots, "tasks": tasks, "complete": self.complete}

    def report(self):
        return {"scenario": self.scenario.to_dict(), "success": self.complete,
                "metrics": {"delivered_tasks": self.state.owners.count(-2),
                            "total_tasks": len(self.scenario.tasks), "timesteps": self.timestep,
                            "total_energy": round(sum(r.battery - self.state.batteries[i]
                                                      for i, r in enumerate(self.scenario.robots)), 9),
                            "transfer_count": sum(e["type"] == "transfer" for e in self.events),
                            "all_home": all(self.state.positions[i] == r.station
                                            for i, r in enumerate(self.scenario.robots))},
                "snapshots": self.snapshots, "events": self.events}
