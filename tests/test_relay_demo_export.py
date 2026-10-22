"""Published animations must come from real checked runs and stay reproducible."""

import hashlib
import json
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from scripts.export_relay_demos import export_demos


def test_export_writes_playable_media_reports_and_a_local_gallery(tmp_path):
    manifest = export_demos(tmp_path, names=["passport_ring", "insufficient_energy"],
                            size=(640, 480), fps=5, tick_seconds=.3)
    assert len(manifest["demos"]) == 2
    for item in manifest["demos"]:
        key = item["id"]
        report = json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8"))
        assert item["metrics"] == report["metrics"]
        assert item["status"] == report["status"]
        assert item["report_sha256"] == hashlib.sha256((tmp_path / f"{key}.json").read_bytes()).hexdigest()
        with Image.open(BytesIO((tmp_path / f"{key}.gif").read_bytes())) as gif:
            assert gif.n_frames > 1
            assert "loop" not in gif.info, "A finished mission must not jump back to its start"
        assert (tmp_path / f"{key}.mp4").read_bytes()[4:8] == b"ftyp"
        assert (tmp_path / f"{key}.png").exists()
    gallery = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<video controls' in gallery
    assert 'passport_ring.mp4' in gallery and 'insufficient_energy.gif' in gallery
    assert (tmp_path / "demos.zip").exists()
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8")) == manifest


def test_export_preserves_previous_results(tmp_path):
    existing = tmp_path / "passport_ring.gif"
    existing.write_bytes(b"previous recording")
    with pytest.raises(FileExistsError):
        export_demos(tmp_path, names=["passport_ring"])
    assert existing.read_bytes() == b"previous recording"


def test_unknown_demo_does_not_write_a_partial_export(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        export_demos(tmp_path, names=["missing"])
    assert not list(tmp_path.iterdir())


def test_append_keeps_previous_recordings_and_includes_both_in_archive(tmp_path):
    export_demos(tmp_path, names=["simple_handoff"], size=(640, 480), fps=3, tick_seconds=.2)
    previous = {path.name: path.read_bytes() for path in tmp_path.glob("simple_handoff.*")}
    manifest = export_demos(tmp_path, names=["insufficient_energy"], append=True,
                            size=(640, 480), fps=3, tick_seconds=.2)
    assert [item["id"] for item in manifest["demos"]] == ["simple_handoff", "insufficient_energy"]
    assert all((tmp_path / name).read_bytes() == data for name, data in previous.items())
    with ZipFile(tmp_path / "demos.zip") as archive:
        assert "simple_handoff.gif" in archive.namelist()
        assert "insufficient_energy.mp4" in archive.namelist()


def test_prepared_demo_is_replayed_and_never_claims_search_optimality(tmp_path, monkeypatch):
    import scripts.export_relay_demos as exporter
    from robotics.relay.examples import example_scenarios
    from robotics.services.relay_service import plan_mission

    actions = plan_mission(example_scenarios()["simple_handoff"])["plan"]["actions"]
    monkeypatch.setattr(exporter, "example_actions", lambda name: actions, raising=False)
    monkeypatch.setattr(exporter, "plan_mission", lambda *a, **k: pytest.fail("prepared plan must be replayed"))
    manifest = export_demos(tmp_path, names=["simple_handoff"], size=(640, 480), fps=3, tick_seconds=.2)
    report = json.loads((tmp_path / "simple_handoff.json").read_text(encoding="utf-8"))
    assert report["success"] and report["status"] == "completed"
    assert not report.get("optimal", False)
    assert manifest["demos"][0]["plan_source"] == "prepared_demo"
