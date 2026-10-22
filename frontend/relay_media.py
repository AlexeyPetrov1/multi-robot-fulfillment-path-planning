"""GIF and H.264 exports of checked snapshots, without changing the mission."""

from collections import defaultdict
from functools import lru_cache
from io import BytesIO
import itertools
import json
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import imageio_ffmpeg
from PIL import GifImagePlugin, Image, ImageDraw, ImageFont, PngImagePlugin

from frontend.relay_view import event_message


COLORS = ("#2563eb", "#e56b19", "#169568", "#9255cf", "#d14686", "#158ea6")
STATUS = {
    "optimal": "План проверен · минимальное число тактов",
    "feasible": "Допустимый план проверен симулятором",
    "completed": "Готовый план проверен симулятором",
    "no_plan": "Допустимый план не найден",
    "horizon_limit": "Достигнут предел числа тактов",
    "time_limit": "Истекло время поиска",
    "state_limit": "Достигнут предел перебора",
    "rejected": "Действие отклонено",
    "incomplete": "Миссия ещё не завершена",
    "dispatch_limit": "Диспетчеру требуется другое решение",
}
ACTIVITY = {"to_pickup": "К грузу", "to_receive": "К встрече", "to_handoff": "К передаче",
            "to_delivery": "Доставка", "returning": "Домой", "home": "На станции",
            "wait": "Ожидание", "complete": "Завершено"}


@lru_cache(maxsize=24)
def _font(size, bold=False):
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold
                 else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    import matplotlib

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name), size)


def _label(draw, xy, text, size=16, color="#273449", bold=False, width=None):
    font = _font(size, bold)
    text = str(text)
    if width and draw.textlength(text, font=font) > width:
        while text and draw.textlength(text + "…", font=font) > width:
            text = text[:-1]
        text += "…"
    draw.text(xy, text, font=font, fill=color, anchor="lt")


def _interpolate(before, after, fraction, coordinates):
    """Interpolate drawing positions; cargo changes only at a checked boundary."""
    old = {r["id"]: r for r in before["robots"]}
    shown = after if fraction >= 1 else before
    robots = []
    for target in after["robots"]:
        rid = target["id"]
        source = old[rid]
        robot = dict(target if fraction >= 1 else source)
        robot["xy"] = tuple(a + (b - a) * fraction for a, b in
                            zip(coordinates[source["position"]], coordinates[target["position"]]))
        robot["battery"] = source["battery"] + (target["battery"] - source["battery"]) * fraction
        robots.append(robot)
    return {**shown, "robots": robots}


def _coordinates(scenario):
    nodes = scenario["nodes"]
    lo_x, hi_x = min(n["x"] for n in nodes), max(n["x"] for n in nodes)
    lo_y, hi_y = min(n["y"] for n in nodes), max(n["y"] for n in nodes)
    if len(nodes) > 40:
        scale = 268 / max(hi_x - lo_x, hi_y - lo_y, 1)
        return {n["id"]: (220 + (n["x"] - (lo_x + hi_x) / 2) * scale,
                           318 - (n["y"] - (lo_y + hi_y) / 2) * scale) for n in nodes}
    sx, sy = 520 / (hi_x - lo_x or 1), 200 / (hi_y - lo_y or 1)
    if hi_x != lo_x and hi_y != lo_y:
        sx, sy = min(sx, sy * 1.7), min(sy, sx * 1.7)
    return {n["id"]: (334 + (n["x"] - (lo_x + hi_x) / 2) * sx,
                       305 - (n["y"] - (lo_y + hi_y) / 2) * sy) for n in nodes}


def _reason(report):
    reason = report.get("reason")
    translations = {
        "All reachable energy-feasible states exhausted.":
            "Варианты исчерпаны: доставка с передачей и безопасным возвратом невозможна.",
        "A required destination is unreachable.": "Одна из необходимых вершин недостижима.",
        "No plan fits the timestep limit.": "Для выполнения миссии нужно больше тактов.",
    }
    return translations.get(reason, STATUS.get(report.get("status"), "Миссия не выполнена"))


def _active_tasks(tasks, limit):
    active = [task for status in ("carried", "pending") for task in tasks if task["status"] == status]
    return active[:limit] if active else tasks[-limit:]


def _map_robots(draw, robots, colors, dense):
    """Keep markers on the graph; move only their readable callouts aside."""
    boxes, dots = [], defaultdict(list)
    right = 389 if dense else 630
    for robot in robots:
        x, y = robot["xy"]
        color = colors[robot["id"]]
        cargo = robot["cargo"]
        text = f"{robot['id']} · {cargo or 'без груза'}"
        width = min(125, max(64, math.ceil(draw.textlength(text, font=_font(11, True))) + 12))
        candidates = []
        for dx, dy in ((8, -28), (8, 9), (-width - 8, -28), (-width - 8, 9),
                       (8, -49), (8, 30), (-width - 8, -49), (-width - 8, 30)):
            left, top = max(45, min(right - width, x + dx)), max(177, min(444, y + dy))
            box = (left, top, left + width, top + 20)
            overlap = sum(max(0, min(box[2], b[2]) - max(box[0], b[0]))
                          * max(0, min(box[3], b[3]) - max(box[1], b[1])) for b in boxes)
            candidates.append((overlap, box))
        box = min(candidates, key=lambda item: item[0])[1]
        boxes.append(box)
        draw.line(((x, y), (max(box[0], min(box[2], x)), max(box[1], min(box[3], y)))),
                  fill=color, width=1)
        draw.rounded_rectangle(box, radius=5, fill="#fff8e8" if cargo else "white", outline=color, width=1)
        _label(draw, (box[0] + 5, box[1] + 4), text, 11, color, True, width - 10)
        dots[(round(x, 4), round(y, 4))].append(color)
    for (x, y), dot_colors in dots.items():
        radius = 5 if dense else 9
        box = (x - radius, y - radius, x + radius, y + radius)
        draw.ellipse(box, fill=dot_colors[0], outline="white", width=1)
        if len(dot_colors) == 2:
            draw.pieslice(box, 270, 90, fill=dot_colors[1], outline="white", width=1)
            draw.ellipse((x - radius - 1, y - radius - 1, x + radius + 1, y + radius + 1),
                         outline="#edac31", width=1)


def _render(report, before, after, fraction, size, pulse=0):
    scenario = report["scenario"]
    dense = len(scenario["nodes"]) > 40
    coordinates = _coordinates(scenario)
    node_names = {node["id"]: node.get("label") or node["id"] for node in scenario["nodes"]}
    task_names = {task["id"]: task.get("label") or task["id"] for task in scenario["tasks"]}
    task_specs = {task["id"]: task for task in scenario["tasks"]}
    moving_before = before
    pickups = {e["task"]: e["robot"] for e in report.get("events", [])
               if before["timestep"] < after["timestep"]
               and e["timestep"] == after["timestep"] and e["type"] == "pickup"}
    if pickups:
        cargo = {robot: task for task, robot in pickups.items()}
        targets = {robot["id"]: robot for robot in after["robots"]}
        intents = {}
        for rid, task in cargo.items():
            target = targets[rid]
            intent = {key: target.get(key) for key in ("activity", "destination", "destination_label")}
            if any(e["type"] == "transfer" and e.get("task") == task
                   and e["timestep"] == after["timestep"] for e in report.get("events", [])):
                intent = {"activity": "to_handoff", "destination": target["position"],
                          "destination_label": node_names[target["position"]]}
            intents[rid] = {**intent, "cargo": task, "cargo_label": task_names[task]}
        moving_before = {
            **before,
            "robots": [{**r, **intents.get(r["id"], {})} for r in before["robots"]],
            "tasks": [{**t, "owner": pickups[t["id"]], "status": "carried"}
                      if t["id"] in pickups else t for t in before["tasks"]],
        }
    frame = _interpolate(moving_before, after, fraction, coordinates)
    image = Image.new("RGB", (960, 640), "#edf2f7")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 132, 644, 474), radius=18, fill="white")
    draw.rounded_rectangle((662, 132, 936, 474), radius=18, fill="white")
    _label(draw, (24, 20), scenario["name"], 27, bold=True, width=912)
    _label(draw, (24, 62), STATUS.get(report.get("status"), "Проверенное воспроизведение"),
           15, "#52647c", width=725)
    badge_color = "#e0ecff" if report["success"] else "#ffe2d6"
    draw.rounded_rectangle((783, 55, 936, 86), radius=12, fill=badge_color)
    draw.ellipse((794, 65, 804, 75), fill=(245, 130 + int(pulse * 70), 72)
                 if not report["success"] else (40, 125 + int(pulse * 65), 145))
    tick = (f"{before['timestep']} → {after['timestep']}" if fraction < 1
            else str(after["timestep"]))
    _label(draw, (813, 63), f"Такт {tick} / {report['snapshots'][-1]['timestep']}", 14, width=115)
    delivered = sum(t["status"] == "delivered" for t in frame["tasks"])
    carried = sum(t["status"] == "carried" for t in frame["tasks"])
    pending = len(frame["tasks"]) - delivered - carried
    if len(frame["tasks"]) > 8:
        tasks = (f"Доставок: {len(frame['tasks'])}   ·   Завершено: {delivered}   ·   "
                 f"В работе: {carried}   ·   Ожидают: {pending}")
    else:
        tasks = "   ·   ".join(f"{task_names[t['id']]}: {node_names[t['pickup']]} → {node_names[t['dropoff']]}"
                                for t in scenario["tasks"][:3]) or "Грузовых задач нет"
        if len(scenario["tasks"]) > 3:
            tasks += f"   ·   ещё {len(scenario['tasks']) - 3}"
    _label(draw, (26, 101), tasks, 15, width=908)
    _label(draw, (42, 149), "Карта склада" if dense else "Маршруты и встречи", 16, bold=True)
    _label(draw, (680, 149), "Роботы и энергия", 16, bold=True)

    for edge in scenario["edges"]:
        a, b = coordinates[edge["source"]], coordinates[edge["target"]]
        draw.line((a, b), fill="#d7e0eb", width=1 if dense else 5)
        if edge.get("cost", 1) != 1 and not dense:
            _label(draw, ((a[0] + b[0]) / 2 + 5, (a[1] + b[1]) / 2 + 5),
                   f"{edge['cost']:g}", 12, "#64748b")
    old = {r["id"]: r for r in before["robots"]}
    for index, robot in enumerate(after["robots"]):
        if old[robot["id"]]["position"] != robot["position"]:
            draw.line((coordinates[old[robot["id"]]["position"]], coordinates[robot["position"]]),
                      fill=COLORS[index % len(COLORS)], width=2 if dense else 3)
    stations = {r["station"] for r in scenario["robots"]}
    goals = {t["dropoff"] for t in frame["tasks"] if t["status"] != "delivered"}
    important_nodes = stations | {t[point] for t in _active_tasks(frame["tasks"], 3)
                                  for point in ("pickup", "dropoff")}
    for node, (x, y) in coordinates.items():
        if node in goals:
            radius = 9 if dense else 21
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="#d2a34b", width=2)
        radius = (5 if node in stations else 2) if dense else 11
        box = (x - radius, y - radius, x + radius, y + radius)
        if node in stations:
            draw.rounded_rectangle(box, radius=4, fill="#d4efe3", outline="#84b39f", width=2)
        else:
            draw.ellipse(box, fill="#e7edf5", outline="#a0afc3", width=2)
        if not dense:
            _label(draw, (x - 16, y + 24), node_names[node], 12, "#64748b", width=100)
        elif node in important_nodes:
            name = node_names[node]
            if name.startswith(("Погрузка ", "Отгрузка ", "Станция ")):
                name = name.rsplit(" ", 1)[-1]
            width = min(100, draw.textlength(name, font=_font(11)))
            _label(draw, (min(x + 8, 389 - width), y + (9 if y < 425 else -15)),
                   name, 11, "#64748b", width=100)
    colors = {r["id"]: COLORS[i % len(COLORS)] for i, r in enumerate(frame["robots"])}
    callouts = dense or any(sum(other["xy"] == robot["xy"] for other in frame["robots"]) > 1
                            for robot in frame["robots"])
    if callouts:
        _map_robots(draw, frame["robots"], colors, dense)
    for index, robot in enumerate(() if callouts else frame["robots"]):
        color = COLORS[index % len(COLORS)]
        x, y = robot["xy"]
        radius = 13 if dense else 18
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline="white", width=2 if dense else 3)
        _label(draw, (x - 10 if dense else x - 12, y - 6 if dense else y - 8),
               robot["id"], 12 if dense else 15, "white", True, 24 if dense else 29)
        if robot["cargo"]:
            top = y + 17 if dense and y < 205 else y - 36 if dense else y - 47
            draw.rounded_rectangle((x - 23, top, x + 23, top + 23), radius=5,
                                   fill="#ffdf9b", outline="#b47c19", width=1)
            _label(draw, (x - 16, top + 4), robot.get("cargo_label") or task_names[robot["cargo"]], 13, "#644318", True, 36)

    row_height = min(93, 280 / len(frame["robots"]))
    compact = len(frame["robots"]) > 3
    for index, robot in enumerate(frame["robots"]):
        y = 183 + index * row_height
        color = COLORS[index % len(COLORS)]
        draw.rounded_rectangle((680, y, 720, y + 23), radius=7, fill=color)
        _label(draw, (686, y + 4), robot["id"], 14, "white", True, 30)
        moving = fraction < 1 and old[robot["id"]]["position"] != after["robots"][index]["position"]
        position = (f"{node_names[old[robot['id']]['position']]} → {node_names[after['robots'][index]['position']]}"
                    if moving else robot.get("position_label") or node_names[robot["position"]])
        _label(draw, (731, y + 4), position, 12, width=180)
        ratio = max(0, min(1, robot["battery"] / robot["capacity"]))
        bar = y + (23 if compact else 27)
        draw.rounded_rectangle((680, bar, 917, bar + 8), radius=4, fill="#e7edf5")
        if ratio:
            draw.rounded_rectangle((680, bar, 680 + 237 * ratio, bar + 8), radius=4, fill=color)
        _label(draw, (680, y + (34 if compact else 40)), f"{robot['battery']:.2f} / {robot['capacity']:g}  ·  {ratio:.0%}", 11 if compact else 13)
        cargo = robot.get("cargo_label") or task_names.get(robot["cargo"], "нет")
        cargo = cargo.split(":", 1)[0].strip()
        _label(draw, (680, y + (47 if compact else 57)), f"Груз: {cargo}", 11 if compact else 13, color, True, 237)
        destination = robot.get("destination") or (task_specs[robot["cargo"]]["dropoff"]
                                                   if robot["cargo"] else robot["station"])
        goal = robot.get("destination_label") or node_names[destination]
        activity = robot.get("activity") or ("Движение" if moving else "На станции" if robot["position"] == robot["station"] else "Ожидание")
        activity = ACTIVITY.get(activity, activity)
        _label(draw, (680, y + (60 if compact else 76)), f"{activity} · Цель: {goal}", 10 if compact else 12, width=237)
    if dense:
        columns = len({n["x"] for n in scenario["nodes"]})
        rows = len({n["y"] for n in scenario["nodes"]})
        _label(draw, (399, 191), f"{columns} × {rows}", 26, bold=True, width=225)
        _label(draw, (399, 229), f"{len(scenario['nodes'])} вершин · {len(scenario['edges'])} рёбер", 12, "#6a7d95", width=225)
        many = len(frame["tasks"]) > 8
        _label(draw, (399, 264), f"Грузы: {delivered}/{len(frame['tasks'])}" if many else "Цели грузов",
               15, bold=True)
        if many:
            _label(draw, (399, 285), f"В работе: {carried} · Ожидают: {pending}", 11, width=225)
        for index, task in enumerate(_active_tasks(frame["tasks"], 4)):
            y = 307 + index * 35 if many else 293 + index * 39
            status = "Доставлен" if task["status"] == "delivered" else f"У {task['owner']}" if task["status"] == "carried" else "Ожидает погрузки"
            name = task_names[task["id"]].split(":", 1)[0].strip()
            title = f"{task['id']} · {name}" if name != task["id"] else task["id"]
            _label(draw, (399, y), f"{title} · {status}", 12, width=225)
            _label(draw, (399, y + 17), f"{node_names[task['pickup']]} → {node_names[task['dropoff']]}",
                   11, "#168363" if task["status"] == "delivered" else "#6a7d95", width=225)
    else:
        _label(draw, (42, 448), "□ Станция     ○ Вершина     ■ Груз     Золотой контур: цель", 11, "#6a7d95", width=582)

    important = [e for e in report.get("events", [])
                 if e["timestep"] == frame["timestep"]
                 and e["type"] in {"transfer", "delivery", "pickup", "rejected"}]
    transfer = any(e["type"] == "transfer" for e in important)
    draw.rounded_rectangle((24, 491, 936, 558), radius=15,
                           fill="#fff0cf" if transfer else "#ffffff")
    _label(draw, (42, 501), "ПЕРЕДАЧА ГРУЗА" if transfer else "СОБЫТИЯ МИССИИ", 11,
           "#8b6a30" if transfer else "#6a7d95", True)
    if not report["success"] and len(report["snapshots"]) == 1:
        text = _reason(report)
    elif important:
        text = " · ".join(event_message(e) for e in important)
    elif frame.get("complete"):
        text = "Грузы доставлены. Все роботы вернулись на свои станции."
    else:
        text = "Роботы движутся к целям" if fraction < 1 else "Старт: все роботы на своих станциях" if frame["timestep"] == 0 else "Движение и ожидание по проверенному плану"
    _label(draw, (42, 522), text, 18, width=875)
    energy = sum(initial["battery"] - robot["battery"]
                 for initial, robot in zip(scenario["robots"], frame["robots"]))
    all_home = all(r["position"] == r["station"] for r in frame["robots"]) and fraction >= 1
    _label(draw, (26, 581), f"Доставлено {delivered}/{len(frame['tasks'])}", 18, bold=True)
    _label(draw, (250, 581), f"Расход энергии {max(0, energy):.1f}", 18, bold=True)
    _label(draw, (562, 581), "Все на станциях" if all_home else "Возврат каждого робота обязателен", 16,
           "#168363" if all_home else "#65768e", True, 372)
    _label(draw, (26, 615), "Один переход по ребру: один такт. Передача и ожидание не расходуют энергию.", 12, "#7a889e", width=908)
    return image.resize(size, Image.Resampling.LANCZOS) if size != image.size else image


def encode_mp4(frames, fps=12):
    """Encode Pillow frames as browser-compatible H.264 with an early moov atom."""
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("fps must be an integer between 1 and 60")
    iterator = iter(frames)
    first = next(iterator, None)
    if not isinstance(first, Image.Image):
        raise ValueError("at least one Pillow frame is required")
    width, height = first.size
    if width % 2 or height % 2 or min(width, height) < 2 or max(width, height) > 4096:
        raise ValueError("video frames need equal even dimensions up to 4096 pixels")
    with TemporaryDirectory(prefix="relay_media_") as directory:
        target = Path(directory) / "mission.mp4"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                   "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}",
                   "-framerate", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", "-y", str(target)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            for index, frame in enumerate(itertools.chain((first,), iterator)):
                if index >= 7200 or not isinstance(frame, Image.Image) or frame.size != first.size:
                    raise ValueError("video frames must have one size; maximum 7200 frames")
                process.stdin.write(frame.convert("RGB").tobytes())
            process.stdin.close()
            process.stdin = None
            _, error = process.communicate(timeout=120)
            if process.returncode:
                raise RuntimeError("Video encoding failed: " + error.decode(errors="replace")[-1000:])
            return target.read_bytes()
        except BaseException:
            process.kill()
            process.communicate()
            raise


def create_media(report, *, size=(960, 640), fps=12, tick_seconds=.8):
    """Render a bounded animation. Failed missions pulse without moving robots."""
    if (not isinstance(size, (tuple, list)) or len(size) != 2
            or any(type(n) is not int or n % 2 for n in size)
            or not 640 <= size[0] <= 1280 or not 480 <= size[1] <= 960):
        raise ValueError("size needs even dimensions between 640x480 and 1280x960")
    if type(fps) is not int or not 1 <= fps <= 30:
        raise ValueError("fps must be an integer between 1 and 30")
    if (isinstance(tick_seconds, bool) or not isinstance(tick_seconds, (int, float))
            or not math.isfinite(tick_seconds) or not .2 <= tick_seconds <= 3):
        raise ValueError("tick_seconds must be between 0.2 and 3")
    if not isinstance(report, dict) or not isinstance(report.get("snapshots"), list) or not report["snapshots"]:
        raise ValueError("report needs at least one checked snapshot")
    snapshots = report["snapshots"]
    if any(snapshot.get("timestep") != tick for tick, snapshot in enumerate(snapshots)):
        raise ValueError("movie history must start at tick 0 and retain consecutive ticks")
    if any(robot.get("position") != robot.get("station") for robot in snapshots[0].get("robots", [])):
        raise ValueError("tick 0 must show every robot at its own station")
    if len(snapshots) > 1001 or not 1 <= len(snapshots[0].get("robots", [])) <= 4:
        raise ValueError("media supports up to 1000 ticks and one to four robots")
    scenario = report.get("scenario", {})
    if not scenario.get("nodes") or len(scenario["nodes"]) > 256:
        raise ValueError("report needs a graph with one to 256 nodes")
    ticks = len(snapshots) - 1
    long = ticks > 200
    if not long and len(snapshots) * fps * tick_seconds > 2400:
        raise ValueError("requested animation exceeds 2400 video frames")
    size = tuple(size)
    gif = BytesIO()
    total_frames = 0
    poster = None
    palette = None

    def emit(before, after, fraction, count, pulse=0):
        nonlocal total_frames, poster, palette
        image = _render(report, before, after, fraction, size, pulse)
        if poster is None:
            poster = image.copy()
        if palette is None:
            palette = image.quantize(colors=192)
            colors = palette.getpalette()
            pulse_colors = [(245, 130 + index * 5, 72) if not report["success"]
                            else (40, 125 + index * 5, 145) for index in range(15)]
            colors[576:621] = list(itertools.chain.from_iterable(pulse_colors))
            palette.putpalette(colors)
        frame = image.quantize(palette=palette, dither=Image.Dither.NONE)
        if total_frames == 0:
            for chunk in GifImagePlugin.getheader(frame, info={"duration": 1})[0]:
                gif.write(chunk)
        duration = (round((total_frames + count) * 100 / fps) * 10
                    - round(total_frames * 100 / fps) * 10)
        for chunk in GifImagePlugin.getdata(frame, duration=duration, disposal=2):
            gif.write(chunk)
        total_frames += count
        for _ in range(count):
            yield image

    def movie_frames():
        first = snapshots[0]
        if len(snapshots) == 1:
            for index in range(4 * fps):
                yield from emit(first, first, 1, 1, (.5 + .5 * math.sin(index * math.tau / fps)))
            return
        yield from emit(first, first, 1, max(1, math.ceil(1.25 * fps)))
        steps = max(1, min(round(fps * tick_seconds), (1000 if long else 480) // ticks))
        highlights = {e["timestep"] for e in report.get("events", []) if e["type"] == "transfer"}
        highlights &= {snapshot["timestep"] for snapshot in snapshots[1:]}
        hold = min(round(.3 * fps), 8 * fps // max(1, len(highlights))) if long else max(1, round(fps))
        repeats = max(1, round(fps * tick_seconds / steps))
        if long:
            available = min(1500, 120 * fps) - max(1, math.ceil(1.25 * fps)) - max(1, round(2 * fps))
            available -= len(highlights) * hold
            maximum = available // (ticks * steps)
            if maximum < 1:
                raise ValueError("fps is too low to retain every tick within two minutes")
            repeats = max(1, min(round(90 * fps / (ticks * steps)), maximum))
        for before, after in zip(snapshots, snapshots[1:]):
            for step in range(1, steps + 1):
                yield from emit(before, after, step / steps, repeats)
            if hold and after["timestep"] in highlights:
                yield from emit(after, after, 1, hold)
        yield from emit(snapshots[-1], snapshots[-1], 1, max(1, round(2 * fps)))

    mp4 = encode_mp4(movie_frames(), fps)
    comment = json.dumps({"fps": fps, "video_frames": total_frames}).encode()
    gif.write(b"!\xfe" + bytes([len(comment)]) + comment + b"\x00;")
    png = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Description", report["scenario"]["name"])
    poster.save(png, format="PNG", pnginfo=metadata)
    return {"gif": gif.getvalue(), "mp4": mp4, "poster": png.getvalue(),
            "duration": total_frames / fps}
