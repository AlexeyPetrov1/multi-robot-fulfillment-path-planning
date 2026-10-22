"""Deliver nine tasks with three simulated robots through a running API.

The API allocates and plans; the existing native executor verifies every joint
move. Verified state and task transitions are then persisted through the API.
The report contains actual execution snapshots for replay, not planned motion.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.api_client import FulfillmentClient  # noqa: E402
from frontend.scenario import grid_layout, robot_bodies, task_bodies  # noqa: E402
from robotics.coordination.conflicts import find_coordination_problems  # noqa: E402
from robotics.coordination.coordinated_executor import CoordinatedExecutor  # noqa: E402
from robotics.coordination.coordination_result import summarise  # noqa: E402
from robotics.coordination.timed_path import TimedPath, TimedStep  # noqa: E402
from robotics.robots.robot import Robot  # noqa: E402
from robotics.services.world import build_warehouse  # noqa: E402
from robotics.simulation.simulator import WarehouseSimulator  # noqa: E402
from robotics.tasks.task import Task, TaskPriority  # noqa: E402
from robotics.warehouse.grid import Position  # noqa: E402


def _coordinate(cell):
    return {"row": cell.row, "col": cell.col}


def _robot_row(robot):
    return {
        "robot_id": robot.robot_id, "position": _coordinate(robot.position),
        "battery_level": robot.battery_level, "status": robot.status.value,
        "payload_capacity": robot.payload_capacity,
        "current_payload": robot.current_payload,
        "assigned_task_id": robot.assigned_task_id,
    }


def _task_row(task):
    return {
        "task_id": task.task_id, "pickup": _coordinate(task.pickup_location),
        "dropoff": _coordinate(task.dropoff_location),
        "status": task.status.value, "assigned_robot_id": task.assigned_robot_id,
        "payload_weight": task.payload_weight, "priority": task.priority.name.lower(),
    }


def _snapshot(report, simulator, wave, phase):
    report["snapshots"].append({
        "timestep": report["metrics"]["timesteps"], "wave": wave, "phase": phase,
        "robots": [_robot_row(r) for r in simulator.robots],
        "tasks": [_task_row(t) for t in simulator.tasks],
    })


def _persist_robots(client, simulator):
    # CRUD updates are sequential. Free the front of a moving chain first;
    # never teleport a robot away to conceal a cyclic simultaneous move.
    stored = {r["robot_id"]: r["position"] for r in client.list_robots()}
    pending = {r.robot_id: _robot_row(r) for r in simulator.robots}
    while pending:
        for rid, row in list(pending.items()):
            if any(pos == row["position"] for other, pos in stored.items() if other != rid):
                continue
            body = {k: v for k, v in row.items() if k != "robot_id"}
            if body["assigned_task_id"] is None:
                body.pop("assigned_task_id")
                body["clear_assigned_task"] = True
            client.update_robot(rid, body)
            stored[rid] = row["position"]
            del pending[rid]
        if pending and all(
            any(pos == row["position"] for other, pos in stored.items() if other != rid)
            for rid, row in pending.items()
        ):
            raise RuntimeError("API cannot persist a cyclic simultaneous move atomically")


def _execute_phase(client, simulator, goals, report, wave, phase, step_delay):
    response = client.plan_coordination({"robots": [
        {"robot_id": r.robot_id, "start": _coordinate(r.position),
         "goal": _coordinate(goals[r.robot_id])}
        for r in simulator.robots
    ]})
    if not response["success"]:
        raise RuntimeError(response.get("failure_reason") or "coordination failed")
    paths = {
        rid: TimedPath.found(rid, [
            TimedStep(Position(s["row"], s["col"]), s["timestep"])
            for s in route["steps"]
        ])
        for rid, route in response["routes"].items() if route["success"]
    }
    if set(paths) != set(goals) or any(
        paths[rid].start != simulator.get_robot(rid).position
        or paths[rid].goal != goal for rid, goal in goals.items()
    ):
        raise RuntimeError("coordination returned incomplete or mismatched routes")
    problems = find_coordination_problems(paths, simulator.warehouse)
    if problems:
        raise RuntimeError("invalid coordinated plan: " + "; ".join(problems))

    makespan = max(p.arrival_time for p in paths.values())
    for timestep in range(1, makespan + 1):
        step_paths = {rid: TimedPath.found(rid, [
            TimedStep(path.position_at(timestep - 1), 0),
            TimedStep(path.position_at(timestep), 1),
        ]) for rid, path in paths.items()}
        segment = summarise(step_paths, sorted(paths), [], 0, 0, 1)
        executed = CoordinatedExecutor(simulator).execute(segment)
        report["metrics"]["vertex_conflicts"] += executed.vertex_conflicts
        report["metrics"]["edge_conflicts"] += executed.edge_conflicts
        if not executed.success or executed.robots_reached_goal != 3:
            raise RuntimeError(executed.failure_reason or "joint execution stopped")
        _persist_robots(client, simulator)
        report["metrics"]["move_steps"] += executed.total_move_steps
        report["metrics"]["timesteps"] += 1
        _snapshot(report, simulator, wave, phase)
        if step_delay:
            time.sleep(step_delay)
    if any(simulator.get_robot(rid).position != goal for rid, goal in goals.items()):
        raise RuntimeError("a robot did not reach its verified goal")
    waits = sum(path.wait_count for path in paths.values())
    report["metrics"]["wait_steps"] += waits
    report["waves"][-1]["phases"].append({
        "phase": phase, "coordination_run_id": response["run_id"],
        "moves": sum(p.move_count for p in paths.values()), "waits": waits,
        "makespan": makespan,
    })


def _validate_trace(report, warehouse):
    paths = {}
    for rid in ("R1", "R2", "R3"):
        steps = []
        for i, snapshot in enumerate(report["snapshots"]):
            robot = next(r for r in snapshot["robots"] if r["robot_id"] == rid)
            pos = robot["position"]
            steps.append(TimedStep(Position(pos["row"], pos["col"]), i))
        paths[rid] = TimedPath.found(rid, steps)
    problems = find_coordination_problems(paths, warehouse)
    if problems:
        raise RuntimeError("executed trace failed validation: " + "; ".join(problems))
    report["metrics"]["trace_validated"] = True


def run(client: FulfillmentClient, *, output: Path | None = None, step_delay: float = 0):
    """Run against an empty fleet/task queue; retain all run rows and history."""
    if step_delay < 0:
        raise ValueError("step_delay must be nonnegative")
    output = Path(output) if output is not None else None
    if output is not None and output.exists():
        raise RuntimeError(f"report already exists: {output}")
    if client.list_robots() or client.list_tasks():
        raise RuntimeError("demo requires empty robots and tasks; existing rows were preserved")
    simulator = WarehouseSimulator(build_warehouse())
    report = {
        "schema_version": 1, "success": False,
        "warehouse": json.loads(json.dumps(grid_layout())),
        "metrics": {"robots": 3, "tasks": 9, "waves": 3, "completed_tasks": 0,
                    "completed_per_robot": {"R1": 0, "R2": 0, "R3": 0},
                    "move_steps": 0, "wait_steps": 0, "timesteps": 0,
                    "vertex_conflicts": 0, "edge_conflicts": 0, "trace_validated": False},
        "snapshots": [], "waves": [],
        "limitations": [
            "Software simulation; no physical robots or real-time guarantees.",
            "A scenario runner orchestrates existing lifecycle methods; the API has no autonomous execution endpoint.",
            "Pickup and unloading are instantaneous simulated actions.",
            "API robot updates are sequential; cyclic simultaneous moves stop the run.",
        ],
    }
    try:
        for body in robot_bodies()[:3]:
            client.create_robot(body)
            pos = body["position"]
            simulator.add_robot(Robot(body["robot_id"], Position(pos["row"], pos["col"])))
        _snapshot(report, simulator, 0, "initialized")
        specs = task_bodies()
        for wave in range(1, 4):
            tasks = []
            for i, spec in enumerate(specs):
                body = {**spec, "task_id": f"T{(wave - 1) * 3 + i + 1}"}
                if wave == 2:
                    body["pickup"], body["dropoff"] = body["dropoff"], body["pickup"]
                client.create_task(body)
                task = Task(
                    body["task_id"], Position(**body["pickup"]), Position(**body["dropoff"]),
                    priority=TaskPriority[body["priority"].upper()],
                    payload_weight=body["payload_weight"],
                )
                simulator.add_task(task)
                tasks.append(task)
            allocation = client.run_allocation({
                "algorithm": "cp_sat", "from_persisted": True, "commit": True,
            })
            assignments = allocation["assignments"]
            if not allocation["committed"] or len(assignments) != 3:
                raise RuntimeError("allocation did not commit all three tasks")
            if {a["task_id"] for a in assignments} != {t.task_id for t in tasks} or len(
                {a["robot_id"] for a in assignments}
            ) != 3:
                raise RuntimeError("allocation is not one task per robot")
            for assignment in assignments:
                simulator.assign_task_manually(assignment["task_id"], assignment["robot_id"])
            report["waves"].append({
                "wave": wave, "allocation_run_id": allocation["run_id"],
                "assignments": assignments, "phases": [],
            })
            _snapshot(report, simulator, wave, "assigned")
            goals = {a["robot_id"]: simulator.get_task(a["task_id"]).pickup_location
                     for a in assignments}
            _execute_phase(client, simulator, goals, report, wave, "pickup", step_delay)
            for assignment in assignments:
                robot = simulator.get_robot(assignment["robot_id"])
                task = simulator.get_task(assignment["task_id"])
                task.start()
                robot.load(task.payload_weight)
                client.update_task(task.task_id, {"status": "in_progress"})
            _persist_robots(client, simulator)
            _snapshot(report, simulator, wave, "loaded")
            goals = {a["robot_id"]: simulator.get_task(a["task_id"]).dropoff_location
                     for a in assignments}
            _execute_phase(client, simulator, goals, report, wave, "delivery", step_delay)
            for assignment in assignments:
                robot = simulator.get_robot(assignment["robot_id"])
                task = simulator.get_task(assignment["task_id"])
                if robot.unload() != task.payload_weight:
                    raise RuntimeError("delivered cargo weight does not match the task")
                task.complete()
                robot.clear_task()
                client.update_task(task.task_id, {"status": "completed"})
            _persist_robots(client, simulator)
            _snapshot(report, simulator, wave, "completed")
        _validate_trace(report, simulator.warehouse)
        final_robots, final_tasks = client.list_robots(), client.list_tasks()
        completed = [t for t in final_tasks if t["status"] == "completed"]
        counts = dict(sorted(Counter(t["assigned_robot_id"] for t in completed).items()))
        report["metrics"].update(completed_tasks=len(completed), completed_per_robot=counts)
        if len(completed) != 9 or counts != {"R1": 3, "R2": 3, "R3": 3}:
            raise RuntimeError("persisted tasks do not confirm three deliveries per robot")
        if any(r["status"] != "idle" or r["assigned_task_id"] is not None
               or r["current_payload"] != 0 for r in final_robots):
            raise RuntimeError("persisted robots are not ready for the next task")
        if any(_robot_row(r) != next(s for s in final_robots if s["robot_id"] == r.robot_id)
               for r in simulator.robots):
            raise RuntimeError("persisted robot state differs from executed state")
        report["success"] = True
        return report
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        report["final_state"] = {"robots": client.list_robots(), "tasks": client.list_tasks()}
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default=os.getenv("FULFILLMENT_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/three_robot_run.json"))
    parser.add_argument("--step-delay", type=float, default=0)
    args = parser.parse_args(argv)
    username = os.getenv("FULFILLMENT_USERNAME") or os.getenv("BOOTSTRAP_ADMIN_USERNAME")
    password = os.getenv("FULFILLMENT_PASSWORD") or os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if not username or not password:
        parser.error("set FULFILLMENT_USERNAME and FULFILLMENT_PASSWORD (or BOOTSTRAP_ADMIN_*)")
    client = FulfillmentClient(base_url=args.api_url)
    client.login(username, password)
    report = run(client, output=args.output, step_delay=args.step_delay)
    print(json.dumps({"success": report["success"], "metrics": report["metrics"],
                      "report": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
