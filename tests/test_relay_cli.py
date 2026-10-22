"""A reproducible mission run must export checked actions without overwriting."""

import json

from robotics.relay.examples import SCENARIO_DIR
from scripts.run_relay_mission import main


def test_cli_runs_real_small_mission_and_preserves_existing_reports(tmp_path):
    output = tmp_path / "run.json"
    args = ["--scenario", str(SCENARIO_DIR / "energy_relay.json"), "--output", str(output)]
    assert main(args) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["success"] and report["metrics"]["timesteps"] == 10
    original = output.read_bytes()
    assert main(args) == 1
    assert output.read_bytes() == original


def test_cli_replays_saved_actions_and_reports_failure(tmp_path):
    bad_actions = tmp_path / "bad.json"
    bad_actions.write_text('[{"moves":{"R1":"v8"}}]', encoding="utf-8")
    output = tmp_path / "rejected.json"
    assert main(["--scenario", str(SCENARIO_DIR / "energy_relay.json"),
                 "--actions", str(bad_actions), "--output", str(output)]) == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "rejected" and report["metrics"]["timesteps"] == 0


def test_cli_continues_saved_execution_without_restarting(tmp_path):
    from robotics.relay.examples import example_scenarios
    from robotics.services.relay_service import plan_mission, replay_mission

    planned = plan_mission(example_scenarios()["energy_relay"])
    prefix = replay_mission(planned["scenario"], planned["plan"]["actions"][:3])
    saved, output = tmp_path / "prefix.json", tmp_path / "continued.json"
    saved.write_text(json.dumps(prefix), encoding="utf-8")
    assert main(["--resume", str(saved), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["metrics"]["timesteps"] == 10
    assert result["metrics"]["total_energy"] == 40
    assert result["plan"]["actions"][:3] == prefix["plan"]["actions"]
