"""Editable scenarios shared by the command line, API and simulator bench."""

import json
from pathlib import Path


SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"


def example_scenarios():
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(SCENARIO_DIR.glob("*.json"))}


def example_actions(name):
    """Optional demonstration schedule; callers must replay it for validation."""
    if name not in example_scenarios():
        raise ValueError(f"unknown example: {name}")
    path = SCENARIO_DIR / "plans" / f"{name}.actions.json"
    if not path.exists():
        return None
    actions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(actions, list):
        raise ValueError("prepared actions must be a list")
    return actions
