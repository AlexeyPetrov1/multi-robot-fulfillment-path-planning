import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


PAGE = Path(__file__).resolve().parents[1] / "frontend/pages/1_Three_robot_run.py"


def test_replay_displays_recorded_positions_and_tasks(tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    robot = {"robot_id": "R1", "position": {"row": 0, "col": 0}, "status": "idle"}
    report.write_text(json.dumps({
        "success": True,
        "warehouse": {"width": 3, "height": 3},
        "metrics": {"robots": 3, "completed_tasks": 9, "vertex_conflicts": 0,
                    "edge_conflicts": 0, "completed_per_robot": {"R1": 3}},
        "snapshots": [
            {"timestep": 0, "wave": 0, "phase": "initialized", "robots": [robot], "tasks": []},
            {"timestep": 1, "wave": 1, "phase": "completed", "robots": [robot],
             "tasks": [{"task_id": "T1", "status": "completed", "assigned_robot_id": "R1"}]},
        ],
    }), encoding="utf-8")
    monkeypatch.setenv("FULFILLMENT_DEMO_REPORT", str(report))
    app = AppTest.from_file(str(PAGE), default_timeout=15).run()
    assert not app.exception
    assert [metric.value for metric in app.metric] == ["3", "9", "0"]
    assert not app.slider
    assert len(app.get("video")) == 1
    assert app.dataframe[1].value.iloc[0]["status"] == "completed"


def test_replay_explains_missing_report(tmp_path, monkeypatch):
    monkeypatch.setenv("FULFILLMENT_DEMO_REPORT", str(tmp_path / "missing.json"))
    app = AppTest.from_file(str(PAGE), default_timeout=15).run()
    assert not app.exception
    assert len(app.info) == 1
