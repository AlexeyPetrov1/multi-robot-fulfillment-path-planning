"""Plan and independently execute a graph mission; return a replayable report."""

from robotics.relay.model import Scenario
from robotics.relay.planner import RelayCoordinator
from robotics.relay.simulator import ActionRejected, MissionSimulator


def _describe(report):
    """Attach presentation hints from checked actions, without changing physics."""
    scenario, frames = report["scenario"], report["snapshots"]
    nodes = {n["id"]: n.get("label") or n["id"] for n in scenario["nodes"]}
    coordinates = {n["id"]: n for n in scenario["nodes"]}
    tasks = {t["id"]: t for t in scenario["tasks"]}
    upcoming = {}
    actions = report["plan"]["actions"][:len(frames) - 1]
    for index in range(len(frames) - 1, -1, -1):
        if index < len(actions):
            action = actions[index]
            previous = {t["id"]: t for t in frames[index]["tasks"]}
            after = {r["id"]: r for r in frames[index + 1]["robots"]}
            # Reverse tick order so pickup remains the first milestone.
            for task_id in action.get("deliveries", []):
                owner = next((t["to"] for t in action.get("transfers", [])
                              if t["task"] == task_id), previous[task_id]["owner"])
                if owner:
                    upcoming[owner] = tasks[task_id]["dropoff"], "to_delivery"
            for transfer in action.get("transfers", []):
                vertex = after[transfer["from"]]["position"]
                upcoming[transfer["from"]] = vertex, "to_handoff"
                upcoming[transfer["to"]] = vertex, "to_receive"
            for task_id, robot in action.get("pickups", {}).items():
                upcoming[robot] = tasks[task_id]["pickup"], "to_pickup"
        for robot in frames[index]["robots"]:
            destination, activity = upcoming.get(robot["id"], (robot["station"], "returning"))
            if robot["position"] == robot["station"] and robot["id"] not in upcoming:
                activity = "home"
            goal = nodes[destination]
            if activity in {"to_handoff", "to_receive"} and not coordinates[destination].get("label"):
                vertex = coordinates[destination]
                goal = f"Встреча ({vertex['x']:g}, {vertex['y']:g})"
            robot.update(position_label=nodes[robot["position"]], station_label=nodes[robot["station"]],
                         destination=destination, destination_label=goal, activity=activity,
                         cargo_label=(tasks[robot["cargo"]].get("label") or robot["cargo"])
                         if robot["cargo"] else None)
        for task in frames[index]["tasks"]:
            task.update(label=tasks[task["id"]].get("label") or task["id"],
                        pickup_label=nodes[task["pickup"]], dropoff_label=nodes[task["dropoff"]])
    for event in report["events"]:
        if event["type"] in {"move", "wait"}:
            event.update(from_label=nodes[event["from"]], to_label=nodes[event["to"]])
        if event.get("task") in tasks:
            task = tasks[event["task"]]
            event.update(task_label=task.get("label") or task["id"],
                         dropoff_label=nodes[task["dropoff"]])
    return report


def _refusals(scenario):
    events = []
    for robot in scenario.robots:
        for task in scenario.tasks:
            distance = (scenario.distance(robot.start, task.pickup)
                        + scenario.distance(task.pickup, task.dropoff)
                        + scenario.distance(task.dropoff, robot.station))
            required = distance * robot.move_cost + robot.capacity * scenario.reserve_fraction
            if required > robot.battery + 1e-8:
                events.append({
                    "timestep": 0, "type": "refusal", "robot": robot.id, "task": task.id,
                    "code": "direct_delivery_energy",
                    "message": f"{robot.id}: энергии на полную доставку {task.id} и возврат недостаточно; возможен участок эстафеты",
                })
    return events


def replay_mission(scenario, actions):
    if not isinstance(actions, list):
        raise ValueError("actions must be a list of joint ticks")
    scenario = Scenario.from_dict(scenario)
    simulator = MissionSimulator(scenario)
    simulator.events.extend(_refusals(scenario))
    rejected = None
    for index, action in enumerate(actions):
        try:
            simulator.step(action)
        except ActionRejected as error:
            rejected = {"action_index": index, "code": error.code, "message": str(error)}
            break
    report = simulator.report()
    report["plan"] = {"actions": actions}
    report["status"] = "rejected" if rejected else "completed" if report["success"] else "incomplete"
    if rejected:
        report["rejected"] = rejected
    return _describe(report)


def _plan(world, *, max_timesteps, max_states, time_limit, strategy, initial_state=None):
    if strategy not in {"auto", "exact", "dispatch"}:
        raise ValueError("unknown planner strategy")
    use_dispatch = strategy == "dispatch" or (strategy == "auto" and
                    (len(world.nodes) > 64 or len(world.tasks) > 6))
    if use_dispatch:
        from robotics.relay.dispatch import RelayDispatcher
        coordinator = RelayDispatcher(world)
    else:
        coordinator = RelayCoordinator(world)
    options = dict(max_timesteps=max_timesteps, max_states=max_states, time_limit=time_limit)
    if initial_state is not None:
        options["initial_state"] = initial_state
    return coordinator.plan(**options)


def _finish_plan(world, plan, prefix=None):
    actions = (prefix or []) + plan.actions
    report = replay_mission(world.to_dict(), actions)
    if report["status"] == "rejected":
        raise RuntimeError("planner produced an invalid action")
    report["plan"] = plan.to_dict()
    report["plan"]["actions"] = actions
    report["status"] = plan.status
    report["optimal"] = plan.optimal
    report["reason"] = plan.reason
    if plan.success and not report["success"]:
        raise RuntimeError("planned mission failed independent execution")
    if not plan.success:
        report["events"].append({"timestep": 0, "type": "refusal", "code": plan.status,
                                 "message": plan.reason or "Не найден допустимый план с передачами и возвратом всех роботов"})
    return report


def plan_mission(scenario, *, max_timesteps=1000, max_states=150000, time_limit=10, strategy="auto"):
    world = Scenario.from_dict(scenario)
    plan = _plan(world, max_timesteps=max_timesteps, max_states=max_states,
                 time_limit=time_limit, strategy=strategy)
    return _finish_plan(world, plan)


def continue_mission(report, *, max_timesteps=1000, max_states=150000,
                     time_limit=10, strategy="auto"):
    """Recheck the executed prefix and plan the remaining total mission horizon."""
    world = Scenario.from_dict(report["scenario"])
    prefix = report["plan"]["actions"]
    checked = replay_mission(world.to_dict(), prefix)
    if checked["status"] == "rejected":
        raise ValueError("Cannot continue a rejected execution prefix")
    if checked["success"]:
        return checked
    if max_timesteps < len(prefix):
        raise ValueError("max_timesteps is shorter than the executed prefix")
    simulator = MissionSimulator(world)
    for action in prefix:
        simulator.step(action)
    plan = _plan(world, max_timesteps=max_timesteps - len(prefix), max_states=max_states,
                 time_limit=time_limit, strategy=strategy, initial_state=simulator.state)
    result = _finish_plan(world, plan, prefix)
    result["optimal"] = False
    result["plan"].update(source="continued", prefix_timesteps=len(prefix),
                          optimal=False, remaining_optimal=plan.optimal)
    if result["success"]:
        result["status"] = "completed"
    return result
