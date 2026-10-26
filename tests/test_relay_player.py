"""The interactive player embeds the checked report as data and never plans."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from frontend.relay_player import player_html, preview_report
from robotics.relay.examples import example_actions, example_scenarios
from robotics.services.relay_service import replay_mission

APP = Path(__file__).resolve().parents[1] / "frontend" / "relay_app.py"


def _embedded(html):
    start = html.index("const REPORT = ") + len("const REPORT = ")
    return json.loads(html[start:html.index(";\nconst OPTIONS")])


def test_player_embeds_every_snapshot_and_event():
    scenario = example_scenarios()["passport_ring"]
    report = replay_mission(scenario, example_actions("passport_ring") or [])
    html = player_html(report)
    data = _embedded(html)
    assert data["snapshots"] == report["snapshots"]
    assert data["events"] == report["events"]
    assert "plan" not in data
    assert "/*__REPORT__*/" not in html and "/*__OPTIONS__*/" not in html


def test_player_cannot_be_broken_out_of_by_scenario_text():
    scenario = json.loads(json.dumps(example_scenarios()["simple_handoff"]))
    scenario["name"] = "</script><script>alert(1)</script>"
    report = replay_mission(scenario, [])
    html = player_html(report)
    assert "</script><script>alert(1)" not in html
    assert _embedded(html)["scenario"]["name"] == scenario["name"]


def test_player_needs_a_checked_snapshot():
    with pytest.raises(ValueError):
        player_html({"scenario": {"nodes": []}, "snapshots": []})


def test_preview_shows_the_initial_state_without_claiming_success():
    scenario = example_scenarios()["energy_relay"]
    initial = replay_mission(scenario, [])["snapshots"][0]
    data = _embedded(player_html(preview_report(scenario, initial)))
    assert data["status"] == "preview" and data["success"] is False
    assert len(data["snapshots"]) == 1


def test_workbench_shows_the_player_before_and_after_a_run(monkeypatch):
    import frontend.relay_workbench as ui

    monkeypatch.setattr(ui, "create_media", lambda report: {"mp4": b"video", "gif": b"GIF89a"})
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert not app.exception
    assert app.get("iframe")
    app.selectbox[0].select("passport_ring").run()
    app.button[0].click().run()
    assert not app.exception
    assert app.get("iframe") and app.get("video")
    labels = [element.proto.label for element in app.get("download_button")]
    assert "Скачать плеер (HTML)" in labels
