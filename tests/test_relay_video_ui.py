"""The workbench serves a native video and reuses encoded media on reruns."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from robotics.relay.examples import example_scenarios

APP = Path(__file__).resolve().parents[1] / "frontend" / "relay_app.py"


@pytest.fixture
def media_stub(monkeypatch, tmp_path):
    import frontend.relay_workbench as ui

    calls = []

    def encode(report, **kwargs):
        calls.append(report["scenario"]["name"])
        return {"mp4": b"test-video", "gif": b"GIF89a-test",
                "poster": b"test-poster", "duration": 4.0}

    monkeypatch.setattr(ui, "create_media", encode, raising=False)
    monkeypatch.setattr(ui, "DEMO_DIR", tmp_path, raising=False)
    if hasattr(ui, "_report_media"):
        ui._report_media.clear()
    return ui, calls, tmp_path


def app_for(example):
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    app.selectbox[0].select(example).run()
    return app


def test_report_has_native_video_downloads_and_all_transfer_events(media_stub):
    app = app_for("passport_ring")
    app.button[0].click().run()
    assert not app.exception
    assert app.get("video")
    assert not app.slider and not app.toggle
    labels = [element.proto.label for element in app.get("download_button")]
    assert "Скачать GIF" in labels
    assert "Скачать MP4" in labels
    events = app.dataframe[-1].value["Событие"].tolist()
    assert sum("передал груз" in message for message in events) == 2
    assert any("доставлен" in message for message in events)


def test_downloads_do_not_rerun_the_page_or_interrupt_playback(media_stub):
    app = app_for("passport_ring")
    app.button[0].click().run()
    assert not app.exception
    assert all(button.proto.ignore_rerun for button in app.get("download_button"))


def test_video_encoding_is_cached_when_unrelated_widgets_change(media_stub):
    _, calls, _ = media_stub
    app = app_for("passport_ring")
    app.button[0].click().run()
    assert len(calls) == 1
    app.run()
    app.number_input[0].set_value(25).run()
    assert not app.exception
    assert len(calls) == 1


def test_no_plan_still_has_honest_video_and_zero_execution(media_stub):
    app = app_for("insufficient_energy")
    app.button[0].click().run()
    assert not app.exception
    assert app.warning and not app.success
    assert app.get("video")
    assert app.metric[1].value == "0"
    assert app.metric[2].value == "0.0"


def test_gallery_shows_existing_video_without_planning_all_examples(media_stub):
    _, calls, demo_dir = media_stub
    (demo_dir / "passport_ring.mp4").write_bytes(b"prepared-video")
    (demo_dir / "passport_ring.gif").write_bytes(b"GIF89a-prepared")
    app = app_for("energy_relay")
    assert not app.exception
    assert app.get("video")
    assert calls == []
    assert len(app.selectbox[0].options) == len(example_scenarios())
    text = " ".join(element.value for element in app.markdown)
    assert example_scenarios()["passport_ring"]["name"] in text


def test_missing_gallery_video_can_build_only_the_clicked_example(media_stub):
    _, calls, _ = media_stub
    app = app_for("energy_relay")
    app.button(key="relay_demo_passport_ring").click().run()
    assert not app.exception
    assert app.selectbox[0].value == "passport_ring"
    assert app.success
    assert len(calls) == 1


def test_gallery_choice_uses_its_example_even_after_a_custom_upload(media_stub, monkeypatch):
    class Upload:
        name = "custom.json"

        def getvalue(self):
            import json

            return json.dumps(example_scenarios()["insufficient_energy"]).encode()

    monkeypatch.setattr(st, "file_uploader", lambda label, **kwargs: Upload()
                        if "отчёт" not in label and kwargs.get("key") in {
                            "relay_scenario_upload", "relay_scenario_upload_0"} else None)
    app = app_for("energy_relay")
    app.button(key="relay_demo_passport_ring").click().run()
    assert not app.exception
    assert app.success
    assert app.metric[0].value == "2/2"


@pytest.fixture
def prepared_ring(media_stub, monkeypatch):
    from robotics.services.relay_service import plan_mission

    ui, _, _ = media_stub
    actions = plan_mission(example_scenarios()["passport_ring"], max_timesteps=8)["plan"]["actions"]
    monkeypatch.setattr(ui, "example_actions", lambda key: actions if key == "passport_ring" else None,
                        raising=False)
    monkeypatch.setattr(ui, "plan_mission", lambda *args, **kwargs:
                        pytest.fail("A prepared replay must not start a fresh search"))
    return ui


def test_prepared_button_rechecks_actions_without_claiming_optimality(prepared_ring):
    app = app_for("passport_ring")
    app.button(key="relay_prepared").click().run()
    assert not app.exception
    assert app.success
    assert app.session_state["relay_report"]["status"] == "completed"
    assert "минималь" not in app.success[0].value
    assert app.metric[0].value == "2/2"
    assert app.get("video")


def test_edited_preset_cannot_use_its_old_prepared_plan(prepared_ring):
    import json

    app = app_for("passport_ring")
    edited = json.loads(app.text_area[0].value)
    edited["robots"][0]["battery"] -= 1
    app.text_area[0].set_value(json.dumps(edited)).run()
    assert not app.exception
    assert not any(button.key == "relay_prepared" for button in app.button)


def test_uploaded_different_graph_cannot_use_selected_presets_plan(prepared_ring, monkeypatch):
    import json

    class Upload:
        name = "another_graph.json"

        def getvalue(self):
            return json.dumps(example_scenarios()["energy_relay"]).encode()

    monkeypatch.setattr(st, "file_uploader", lambda label, **kwargs:
                        None if "отчёт" in label else Upload())
    app = app_for("passport_ring")
    assert not app.exception
    assert not any(button.key == "relay_prepared" for button in app.button)


def test_invalid_prepared_actions_are_rejected_by_fresh_replay(prepared_ring, monkeypatch):
    monkeypatch.setattr(prepared_ring, "example_actions",
                        lambda key: [{"moves": {"R1": "missing"}}])
    app = app_for("passport_ring")
    app.button(key="relay_prepared").click().run()
    assert not app.exception
    assert not app.success
    assert app.warning
    assert app.session_state["relay_report"]["status"] == "rejected"
    assert app.metric[1].value == "0"


def test_grid16_prepared_run_checks_all_four_robots_without_search(media_stub, monkeypatch):
    ui, _, _ = media_stub
    monkeypatch.setattr(ui, "plan_mission", lambda *args, **kwargs:
                        pytest.fail("The large prepared demonstration must use replay"))
    app = app_for("grid16_team4")
    app.button(key="relay_prepared").click().run()
    assert not app.exception
    report = app.session_state["relay_report"]
    assert report["success"] and report["status"] == "completed"
    assert report["optimal"] is False
    assert len(report["scenario"]["nodes"]) == 256
    assert len(report["scenario"]["edges"]) == 480
    assert report["metrics"]["delivered_tasks"] == report["metrics"]["total_tasks"] == 4
    assert report["metrics"]["timesteps"] == 85
    assert all(len(frame["robots"]) == 4 for frame in report["snapshots"])
    assert all(robot["position"] == robot["station"]
               and robot["battery"] >= robot["capacity"] * .1
               for robot in report["snapshots"][-1]["robots"])
    assert app.get("video")


@pytest.fixture
def published_run(media_stub):
    import json
    from copy import deepcopy
    from robotics.relay.examples import example_actions
    from robotics.services.relay_service import replay_mission

    ui, calls, demo_dir = media_stub
    report = replay_mission(example_scenarios()["grid16_team4"], example_actions("grid16_team4"))
    (demo_dir / "grid16_team4.json").write_text(json.dumps(report), encoding="utf-8")
    (demo_dir / "grid16_team4.mp4").write_bytes(b"published-video")
    (demo_dir / "grid16_team4.gif").write_bytes(b"GIF89a-published")
    # Runtime-only provenance must not trigger expensive re-encoding.
    current = deepcopy(report)
    current["optimal"] = False
    current["plan"].update(source="prepared", optimal=False)
    return ui, calls, demo_dir, current


def test_exact_published_run_reuses_media_without_encoding(published_run):
    import json

    ui, calls, _, report = published_run
    media = ui._report_media(json.dumps(report), "grid16_team4")
    assert media["mp4"] == b"published-video"
    assert media["gif"] == b"GIF89a-published"
    assert calls == []


def test_fresh_dispatch_with_identical_execution_reuses_checked_recording(published_run):
    import json

    ui, calls, _, report = published_run
    report["status"] = "feasible"
    report["plan"].pop("source", None)
    media = ui._report_media(json.dumps(report), "grid16_team4")
    assert media["mp4"] == b"published-video"
    assert calls == []


def test_workbench_can_calculate_a_large_route_without_using_prepared_actions(published_run, monkeypatch):
    ui, calls, _, _ = published_run
    monkeypatch.setattr(ui, "example_actions", lambda key: None)
    app = app_for("grid16_team4")
    next(button for button in app.button if button.label == "Построить и проверить план").click().run()
    assert not app.exception
    report = app.session_state["relay_report"]
    assert report["success"] and report["status"] == "feasible"
    assert report["metrics"]["delivered_tasks"] == 4
    assert report["metrics"]["all_home"]
    assert calls == [], "An identical checked execution should not encode the long video again"


@pytest.mark.parametrize("changed", ["scenario", "actions", "snapshots", "status", "metrics"])
def test_stale_published_run_is_never_used_for_another_execution(published_run, changed):
    import json

    ui, calls, _, report = published_run
    if changed == "scenario":
        report["scenario"]["robots"][0]["battery"] -= 1
    elif changed == "actions":
        report["plan"]["actions"] = report["plan"]["actions"][1:]
    elif changed == "snapshots":
        report["snapshots"][0]["robots"][0]["battery"] -= 1
    elif changed == "status":
        report["status"] = "optimal"
    else:
        report["metrics"]["total_energy"] += 1
    media = ui._report_media(json.dumps(report), "grid16_team4")
    assert media["mp4"] == b"test-video"
    assert len(calls) == 1


def test_published_video_needs_both_formats_and_a_valid_matching_report(published_run):
    import json

    ui, calls, demo_dir, report = published_run
    (demo_dir / "grid16_team4.json").write_text("{", encoding="utf-8")
    media = ui._report_media(json.dumps(report), "grid16_team4")
    assert media["mp4"] == b"test-video"
    assert len(calls) == 1


def test_prepared_ui_uses_published_media_after_fresh_validation(published_run, monkeypatch):
    ui, calls, _, _ = published_run
    monkeypatch.setattr(ui, "plan_mission", lambda *args, **kwargs:
                        pytest.fail("Prepared execution must not start a search"))
    app = app_for("grid16_team4")
    app.button(key="relay_prepared").click().run()
    assert not app.exception
    assert app.session_state["relay_report"]["status"] == "completed"
    assert app.metric[0].value == "4/4"
    assert calls == []
    assert app.get("video")


def test_twenty_five_deliveries_replay_on_one_initial_charge(media_stub, monkeypatch):
    ui, _, _ = media_stub
    monkeypatch.setattr(ui, "plan_mission", lambda *a, **k: pytest.fail("Prepared playback must use replay"))
    app = app_for("grid16_team4_25")
    app.button(key="relay_prepared").click().run()
    assert not app.exception
    report = app.session_state["relay_report"]
    assert report["success"] and report["status"] == "completed"
    assert len(report["scenario"]["tasks"]) == 25
    assert app.metric[0].value == "25/25"
    assert all("charges" not in action for action in report["plan"]["actions"])
    for before, after in zip(report["snapshots"], report["snapshots"][1:]):
        assert len(after["robots"]) == 4
        assert all(b["battery"] <= a["battery"] for a, b in zip(before["robots"], after["robots"]))
    assert report["metrics"]["all_home"]
    assert all(task["handed"] for task in report["snapshots"][-1]["tasks"])
    assert app.get("video")
