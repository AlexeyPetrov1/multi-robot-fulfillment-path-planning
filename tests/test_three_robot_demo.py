"""The live-API demo must deliver cargo, preserve traces, and fail honestly."""

import json

import pytest

from frontend.api_client import FulfillmentClient
from robotics.coordination.conflicts import find_coordination_problems
from robotics.coordination.timed_path import TimedPath, TimedStep
from robotics.services.world import build_warehouse
from robotics.warehouse.grid import Position
from scripts.run_three_robot_demo import run


@pytest.fixture
def client(api_client):
    return FulfillmentClient(_client=api_client)


def test_three_robots_deliver_three_tasks_each_through_api(client, tmp_path):
    output = tmp_path / "run.json"
    report = run(client, output=output)
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["success"] is True
    assert report["metrics"]["completed_tasks"] == 9
    assert report["metrics"]["completed_per_robot"] == {"R1": 3, "R2": 3, "R3": 3}
    assert len(report["waves"]) == 3
    assert all(w["allocation_run_id"] > 0 for w in report["waves"])
    assert len(client.list_robots()) == 3
    assert len(client.list_tasks()) == 9
    assert all(t["status"] == "completed" for t in client.list_tasks())
    for robot in client.list_robots():
        assert robot["status"] == "idle"
        assert robot["assigned_task_id"] is None
        assert robot["current_payload"] == 0
        assert 0 < robot["battery_level"] < 100

    snapshots = report["snapshots"]
    traces = {}
    for rid in ("R1", "R2", "R3"):
        cells = [next(r for r in s["robots"] if r["robot_id"] == rid) for s in snapshots]
        traces[rid] = TimedPath.found(rid, [
            TimedStep(Position(r["position"]["row"], r["position"]["col"]), i)
            for i, r in enumerate(cells)
        ])
        moves = sum(a["position"] != b["position"] for a, b in zip(cells, cells[1:]))
        assert cells[-1]["battery_level"] == pytest.approx(100 - moves)
    assert find_coordination_problems(traces, build_warehouse()) == []
    loaded = [s for s in snapshots if s["phase"] == "loaded"]
    assert len(loaded) == 3
    assert all(r["current_payload"] > 0 for s in loaded for r in s["robots"])
    assert report["metrics"]["trace_validated"] is True
    assert report["metrics"]["move_steps"] > 0


def test_refuses_to_replace_existing_state(client):
    original = client.create_robot({"robot_id": "existing", "position": {"row": 0, "col": 0}})
    with pytest.raises(RuntimeError, match="empty"):
        run(client)
    assert client.list_robots() == [original]
    assert client.list_tasks() == []


def test_failed_plan_does_not_mark_a_delivery_complete(client, monkeypatch, tmp_path):
    monkeypatch.setattr(client, "plan_coordination", lambda body: {
        "success": False, "failure_reason": "blocked test route", "routes": {},
    })
    output = tmp_path / "failed.json"
    with pytest.raises(RuntimeError, match="blocked test route"):
        run(client, output=output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["success"] is False
    assert all(t["status"] == "assigned" for t in client.list_tasks())
    assert all(r["battery_level"] == 100 for r in client.list_robots())


def test_failed_execution_does_not_start_or_complete_tasks(client, monkeypatch):
    from robotics.coordination.coordinated_executor import CoordinatedExecutionResult

    monkeypatch.setattr(
        "scripts.run_three_robot_demo.CoordinatedExecutor.execute",
        lambda *_: CoordinatedExecutionResult(success=False, failure_reason="battery test stop"),
    )
    with pytest.raises(RuntimeError, match="battery test stop"):
        run(client)
    assert all(t["status"] == "assigned" for t in client.list_tasks())
    assert all(r["current_payload"] == 0 for r in client.list_robots())
