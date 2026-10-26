"""Interactive browser playback of a checked mission report.

The player is one self-contained HTML page (frontend/static/relay_player.html)
with the report embedded as JSON. It only interpolates between checked
snapshots; it never plans, moves or validates anything itself.
"""

import json
from functools import lru_cache
from pathlib import Path

import streamlit as st


TEMPLATE = Path(__file__).resolve().parent / "static" / "relay_player.html"
KEEP = ("scenario", "success", "metrics", "snapshots", "events", "status", "reason")


@lru_cache(maxsize=1)
def _template():
    return TEMPLATE.read_text(encoding="utf-8")


def _embed(value):
    # Safe inside <script>: no closing tags, no HTML comment openers, no line separators.
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def player_html(report, *, autoplay=False, map_height=460):
    """Return the standalone player page for a report (also usable as a download)."""
    if not isinstance(report, dict) or not report.get("snapshots"):
        raise ValueError("report needs at least one checked snapshot")
    data = {key: report.get(key) for key in KEEP}
    data["events"] = data["events"] or []
    options = {"autoplay": bool(autoplay), "mapHeight": int(map_height)}
    return (_template().replace("/*__REPORT__*/null", _embed(data))
            .replace("/*__OPTIONS__*/{}", _embed(options)))


def preview_report(scenario, snapshot):
    """A single-frame report for a scenario that has not been planned yet."""
    return {"scenario": scenario, "success": False, "status": "preview", "reason": None,
            "metrics": {}, "snapshots": [snapshot], "events": []}


def render_player(report, *, autoplay=False, map_height=None):
    dense = len(report["scenario"]["nodes"]) > 40
    map_height = map_height or (560 if dense else 420)
    # Streamlit measures the page and sizes the iframe to fit it.
    st.iframe(player_html(report, autoplay=autoplay, map_height=map_height), height="content")
