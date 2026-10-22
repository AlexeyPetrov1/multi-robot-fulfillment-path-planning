"""Exported animations retain checked cargo states and play as real H.264."""

from copy import deepcopy
from io import BytesIO
import subprocess

import imageio_ffmpeg
from PIL import Image, ImageChops
import pytest

from frontend.relay_media import create_media, encode_mp4, _interpolate
from robotics.services.relay_service import replay_mission


@pytest.fixture
def report():
    scenario = {
        "name": "Доставка с передачей груза",
        "nodes": [{"id": n, "x": i, "y": 0} for i, n in enumerate("ABC")],
        "edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
        "robots": [{"id": rid, "station": station, "capacity": 10,
                    "battery": 10, "move_cost": 1}
                   for rid, station in (("R1", "A"), ("R2", "C"))],
        "tasks": [{"id": "T1", "pickup": "A", "dropoff": "C"}],
    }
    actions = [
        {"pickups": {"T1": "R1"}, "moves": {"R1": "B", "R2": "B"},
         "transfers": [{"task": "T1", "from": "R1", "to": "R2"}]},
        {"moves": {"R1": "A", "R2": "C"}, "deliveries": ["T1"]},
    ]
    return replay_mission(scenario, actions)


@pytest.fixture
def media(report):
    return create_media(report, size=(640, 480), fps=4, tick_seconds=.5)


def _decode_movie(data, tmp_path):
    movie = tmp_path / "mission.mp4"
    movie.write_bytes(data)
    result = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(movie), "-f", "framemd5", "-"],
        capture_output=True, check=True,
    )
    hashes = [line.rsplit(",", 1)[-1].strip()
              for line in result.stdout.decode().splitlines() if line and not line.startswith("#")]
    return result.stderr.decode(errors="replace"), hashes


def test_animation_plays_once_with_timing_poster_and_distinct_states(media):
    gif = Image.open(BytesIO(media["gif"]))
    assert gif.size == (640, 480)
    assert gif.n_frames > 3 and "loop" not in gif.info
    duration = 0
    for index in range(gif.n_frames):
        gif.seek(index)
        duration += gif.info["duration"] / 1000
    assert duration == pytest.approx(media["duration"], abs=.1)
    poster = Image.open(BytesIO(media["poster"]))
    assert poster.format == "PNG" and poster.size == gif.size


def test_mp4_is_h264_faststart_and_every_frame_decodes(media, tmp_path):
    metadata, hashes = _decode_movie(media["mp4"], tmp_path)
    assert "h264" in metadata and "yuv420p" in metadata
    assert len(hashes) == round(media["duration"] * 4)
    assert len(set(hashes)) > 3 and hashes[0] != hashes[-1]
    assert media["mp4"].index(b"moov") < media["mp4"].index(b"mdat")


def test_interpolation_changes_cargo_only_at_the_checked_tick_boundary(report):
    before, after = report["snapshots"][:2]
    coordinates = {"A": (0, 0), "B": (50, 0), "C": (100, 0)}
    middle = _interpolate(before, after, .5, coordinates)
    arrived = _interpolate(before, after, 1, coordinates)
    assert [r["cargo"] for r in middle["robots"]] == [r["cargo"] for r in before["robots"]]
    assert [r["cargo"] for r in arrived["robots"]] == [r["cargo"] for r in after["robots"]]
    assert [r["xy"] for r in arrived["robots"]] == [coordinates["B"], coordinates["B"]]
    assert middle["robots"][0]["xy"] != coordinates["A"]


def test_pickup_travels_with_sender_until_the_arrival_handoff(report, monkeypatch):
    import frontend.relay_media as media

    original = deepcopy(report)
    scenes = []
    interpolate = media._interpolate

    def observe(*args):
        scene = interpolate(*args)
        scenes.append(scene)
        return scene

    monkeypatch.setattr(media, "_interpolate", observe)
    before, after = report["snapshots"][:2]
    media._render(report, before, after, .5, (640, 480))
    media._render(report, before, after, 1, (640, 480))

    assert [r["cargo"] for r in scenes[0]["robots"]] == ["T1", None]
    assert [r["cargo"] for r in scenes[1]["robots"]] == [None, "T1"]
    assert report == original


def test_render_does_not_mutate_the_checked_report(report):
    original = deepcopy(report)
    create_media(report, size=(640, 480), fps=4, tick_seconds=.25)
    assert report == original


def test_failed_mission_pulses_without_inventing_robot_movement(report):
    failed = deepcopy(report)
    failed["snapshots"] = failed["snapshots"][:1]
    failed.update(success=False, status="no_plan", reason="All reachable energy-feasible states exhausted.")
    failed["metrics"].update(delivered_tasks=0, timesteps=0, total_energy=0, transfer_count=0)
    failed["events"] = []
    media = create_media(failed, size=(640, 480), fps=4)
    gif = Image.open(BytesIO(media["gif"]))
    assert gif.n_frames > 1 and 3 <= media["duration"] <= 5
    gif.seek(0)
    graph = gif.convert("RGB").crop((20, 100, 330, 320))
    for index in range(gif.n_frames):
        gif.seek(index)
        assert ImageChops.difference(graph, gif.convert("RGB").crop((20, 100, 330, 320))).getbbox() is None
    assert failed["snapshots"][0]["timestep"] == 0


@pytest.mark.parametrize("options", [{"size": (641, 480)}, {"size": (10, 10)},
                                    {"fps": 0}, {"tick_seconds": float("nan")}])
def test_invalid_media_options_fail_clearly(report, options):
    with pytest.raises(ValueError):
        create_media(report, **options)


def test_missing_snapshots_are_rejected(report):
    report["snapshots"] = []
    with pytest.raises(ValueError, match="snapshot"):
        create_media(report)


def test_public_video_encoder_accepts_pillow_frames(tmp_path):
    frames = [Image.new("RGB", (64, 48), color) for color in ("red", "green", "blue")]
    metadata, hashes = _decode_movie(encode_mp4(frames, fps=3), tmp_path)
    assert "h264" in metadata and len(hashes) == 3
    assert len(set(hashes)) == 3


def test_dense_grid_with_four_robots_encodes_without_a_label_cloud(tmp_path, monkeypatch):
    import frontend.relay_media as media

    side = 16
    node = lambda x, y: f"n{x}_{y}"
    scenario = {
        "name": "Склад 16×16: четыре робота",
        "nodes": [{"id": node(x, y), "x": x, "y": y}
                  for y in range(side) for x in range(side)],
        "edges": [{"source": node(x, y), "target": node(nx, ny)}
                  for y in range(side) for x in range(side)
                  for nx, ny in ((x + 1, y), (x, y + 1)) if nx < side and ny < side],
        "robots": [{"id": f"R{i + 1}", "station": node(x, y), "capacity": 100,
                    "battery": 100, "move_cost": 1}
                   for i, (x, y) in enumerate(((0, 0), (15, 15), (0, 15), (15, 0)))],
        "tasks": [{"id": "T1", "pickup": node(0, 0), "dropoff": node(15, 15)}]
                 + [{"id": f"T{i + 2}", "pickup": node(i + 1, 7), "dropoff": node(15, 15)}
                    for i in range(12)],
    }
    report = replay_mission(scenario, [{"pickups": {"T1": "R1"}, "moves": {"R1": node(1, 0)}}])
    original = deepcopy(report)
    labels = []
    draw_label = media._label

    def observe(draw, xy, text, *args, **kwargs):
        labels.append(str(text))
        draw_label(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(media, "_label", observe)
    encoded = create_media(report, fps=4, tick_seconds=.5)

    coordinates = media._coordinates(scenario)
    xs, ys = zip(*coordinates.values())
    assert max(xs) - min(xs) == pytest.approx(max(ys) - min(ys))
    assert len(set(labels) & {n["id"] for n in scenario["nodes"]}) <= 10
    assert {"R1", "R2", "R3", "R4"} <= set(labels)
    metadata, hashes = _decode_movie(encoded["mp4"], tmp_path)
    assert "h264" in metadata and len(hashes) == round(encoded["duration"] * 4)
    assert Image.open(BytesIO(encoded["gif"])).n_frames > 1
    assert report == original


def test_prepared_movie_does_not_claim_delivery_in_its_initial_frame(report, monkeypatch):
    import frontend.relay_media as media

    report = deepcopy(report)
    report["status"] = "completed"
    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs: labels.append(str(text)))
    initial = report["snapshots"][0]
    media._render(report, initial, initial, 1, (640, 480))
    assert "Все грузы доставлены, роботы вернулись" not in labels
    assert any("проверен" in text.lower() for text in labels)


@pytest.mark.parametrize(("ticks", "highlights"), [(481, 0), (719, 75), (1000, 0)])
def test_long_movie_retains_every_checked_tick_with_bounded_frames(report, monkeypatch, ticks, highlights):
    import weakref
    import frontend.relay_media as media

    long = deepcopy(report)
    long["snapshots"] = [{**deepcopy(report["snapshots"][-1]), "timestep": t}
                         for t in range(ticks + 1)]
    long["events"] = [{"timestep": tick, "type": "transfer"} for tick in range(1, highlights + 1)]
    long["metrics"]["timesteps"] = ticks
    seen, live, peak = [], [], [0]

    def render(report, before, after, fraction, size, pulse=0):
        seen.append((after["timestep"], fraction))
        return Image.new("RGB", (64, 48), "white")

    quantize = Image.Image.quantize

    def watch(self, *args, **kwargs):
        image = quantize(self, *args, **kwargs)
        live.append(weakref.ref(image))
        peak[0] = max(peak[0], sum(ref() is not None for ref in live))
        return image

    encoded_frames = [0]

    def encode(frames, fps):
        encoded_frames[0] = sum(1 for _ in frames)
        return b"checked-video"

    monkeypatch.setattr(media, "_render", render)
    monkeypatch.setattr(media, "encode_mp4", encode)
    monkeypatch.setattr(Image.Image, "quantize", watch)
    result = media.create_media(long)
    assert set(range(ticks + 1)) <= {tick for tick, fraction in seen if fraction == 1}
    assert len(seen) <= 1500
    assert encoded_frames[0] <= 1500
    assert 60 <= result["duration"] <= 120
    assert peak[0] < 20, "GIF export must not retain every uncompressed palette frame"
    gif = Image.open(BytesIO(result["gif"]))
    assert gif.n_frames >= ticks + 1


def test_dense_movie_lists_active_cargo_and_progress_instead_of_first_four(monkeypatch):
    import frontend.relay_media as media
    from robotics.relay.examples import example_actions, example_scenarios

    base = replay_mission(example_scenarios()["grid16_team4"], example_actions("grid16_team4"))
    frame = deepcopy(base["snapshots"][0])
    template = frame["tasks"][0]
    frame["tasks"] = [{**template, "id": f"T{i}", "status": "delivered" if i <= 20 else "pending"}
                      for i in range(1, 26)]
    frame["tasks"][20].update(status="carried", owner="R1")
    frame["robots"][0]["cargo"] = "T21"
    base["scenario"]["tasks"] = [{"id": t["id"], "pickup": t["pickup"], "dropoff": t["dropoff"]}
                                   for t in frame["tasks"]]
    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs: labels.append(str(text)))
    media._render(base, frame, frame, 1, (960, 640))
    assert any(text.startswith("T21 ·") for text in labels)
    assert "Доставлено 20/25" in labels
    assert any("В работе: 1" in text and "Ожидают: 4" in text for text in labels)


def test_a_short_partial_run_keeps_its_tempo_even_with_25_pending_deliveries(report):
    scenario = deepcopy(report["scenario"])
    scenario["tasks"] = [{**scenario["tasks"][0], "id": f"T{i}"} for i in range(1, 26)]
    partial = replay_mission(scenario, report["plan"]["actions"])
    encoded = create_media(partial, size=(640, 480), fps=4, tick_seconds=.5)
    assert partial["status"] == "incomplete"
    assert encoded["duration"] < 10


@pytest.fixture(scope="module")
def grid25():
    from robotics.relay.examples import example_actions, example_scenarios

    report = replay_mission(example_scenarios()["grid16_team4_25"],
                            example_actions("grid16_team4_25"))
    assert report["success"]
    return report


def test_dense_robots_and_cargo_labels_stay_on_the_moving_map(grid25, monkeypatch):
    import frontend.relay_media as media

    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs:
                        labels.append((xy, str(text))))
    meetings = []
    for frame in grid25["snapshots"]:
        positions = [r["position"] for r in frame["robots"]]
        if len(set(positions)) < len(positions):
            meetings.append(frame)
    assert meetings
    for frame in (meetings[0], meetings[-1]):
        labels.clear()
        media._render(grid25, frame, frame, 1, (960, 640))
        map_labels = {text for (x, y), text in labels if 24 <= x < 393 and 175 <= y < 470}
        for robot in frame["robots"]:
            cargo = robot["cargo"] or "без груза"
            assert any(robot["id"] in text and cargo in text
                       for text in map_labels)
        assert not any("Встреча двух роботов" == text for _, text in labels)


def test_interpolation_is_continuous_through_pickups_handoffs_and_delivery(report):
    import frontend.relay_media as media

    coordinates = media._coordinates(report["scenario"])
    for before, after in zip(report["snapshots"], report["snapshots"][1:]):
        for fraction in (0, .25, .5, .75, 1):
            robots = media._interpolate(before, after, fraction, coordinates)["robots"]
            for source, target, robot in zip(before["robots"], after["robots"], robots):
                expected = tuple(a + (b - a) * fraction for a, b in
                                 zip(coordinates[source["position"]], coordinates[target["position"]]))
                assert robot["xy"] == pytest.approx(expected)


def test_movie_starts_with_a_visible_home_state_and_never_resets(report, monkeypatch):
    import frontend.relay_media as media

    emitted = []
    calls = []

    def render(report, before, after, fraction, size, pulse=0):
        calls.append((before["timestep"], after["timestep"], fraction))
        return Image.new("RGB", (64, 48), (after["timestep"], 0, 0))

    def encode(frames, fps):
        emitted.extend(frame.getpixel((0, 0))[0] for frame in frames)
        return b"checked-video"

    monkeypatch.setattr(media, "_render", render)
    monkeypatch.setattr(media, "encode_mp4", encode)
    media.create_media(report, fps=4)
    assert all(robot["position"] == robot["station"] for robot in report["snapshots"][0]["robots"])
    assert emitted[:4] == [0] * 4
    assert emitted == sorted(emitted)
    assert {(0, 1), (1, 2)} <= {(before, after) for before, after, _ in calls}


def test_named_targets_cargo_and_live_activity_are_visible(report, monkeypatch):
    import frontend.relay_media as media

    report = deepcopy(report)
    report["scenario"]["nodes"][2]["label"] = "Получатель"
    report["scenario"]["tasks"][0]["label"] = "Посылка"
    frame = report["snapshots"][1]
    frame["robots"][1].update(destination="C", destination_label="Получатель",
                              activity="to_delivery", cargo_label="Посылка")
    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs:
                        labels.append(str(text)))
    media._render(report, frame, frame, 1, (960, 640))
    assert "Груз: Посылка" in labels
    assert any("Получатель" in text and "Цель" in text for text in labels)
    assert "Доставка · Цель: Получатель" in labels


def test_a_moving_robot_shows_the_current_edge(report, monkeypatch):
    import frontend.relay_media as media

    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs:
                        labels.append(str(text)))
    media._render(report, report["snapshots"][0], report["snapshots"][1], .5, (960, 640))
    assert {"A → B", "C → B"} <= set(labels)


def test_pickup_motion_points_to_the_handoff_instead_of_the_completed_pickup(report, monkeypatch):
    import frontend.relay_media as media

    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs:
                        labels.append(str(text)))
    media._render(report, report["snapshots"][0], report["snapshots"][1], .5, (960, 640))
    assert "К передаче · Цель: B" in labels


def test_long_order_names_leave_the_id_and_full_route_readable(grid25, monkeypatch):
    import frontend.relay_media as media

    report = deepcopy(grid25)
    frame = next(frame for frame in report["snapshots"] if any(r["cargo"] for r in frame["robots"]))
    robot = next(r for r in frame["robots"] if r["cargo"])
    task = next(t for t in report["scenario"]["tasks"] if t["id"] == robot["cargo"])
    task["label"] = "Заказ 01: Погрузка П1 → Отгрузка О1"
    robot["cargo_label"] = task["label"]
    for node in report["scenario"]["nodes"]:
        if node["id"] in (task["pickup"], task["dropoff"]):
            node["label"] = "Погрузка П1" if node["id"] == task["pickup"] else "Отгрузка О1"
    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs: labels.append(str(text)))
    media._render(report, frame, frame, 1, (960, 640))
    assert f"{robot['id']} · {robot['cargo']}" in labels
    assert "Погрузка П1 → Отгрузка О1" in labels
    assert any(text.startswith(f"{task['id']} · Заказ 01 ·") for text in labels)


def test_dense_landmarks_use_readable_codes_inside_the_map_column(grid25, monkeypatch):
    import frontend.relay_media as media

    labels = []
    monkeypatch.setattr(media, "_label", lambda draw, xy, text, *args, **kwargs:
                        labels.append((xy, str(text))))
    frame = grid25["snapshots"][0]
    media._render(grid25, frame, frame, 1, (960, 640))
    map_labels = [(xy, text) for xy, text in labels if xy[0] < 393 and 175 < xy[1] < 470]
    assert {"П1", "О1"} <= {text for xy, text in map_labels}
    draw = media.ImageDraw.Draw(Image.new("RGB", (960, 640)))
    for (x, y), text in map_labels:
        assert x + draw.textlength(text, font=media._font(11)) <= 390


@pytest.mark.parametrize("corruption", ["start", "missing_tick", "center"])
def test_a_movie_rejects_a_cut_or_reordered_history(report, corruption):
    report = deepcopy(report)
    if corruption == "start":
        report["snapshots"] = report["snapshots"][1:]
    elif corruption == "missing_tick":
        report["snapshots"][1]["timestep"] = 3
    else:
        report["snapshots"][0]["robots"][0]["position"] = "B"
    with pytest.raises(ValueError, match="tick 0|consecutive|station"):
        create_media(report)
