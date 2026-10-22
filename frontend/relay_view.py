"""Presentation of checked mission snapshots; no state changes happen here."""

from collections import defaultdict

import matplotlib.pyplot as plt


COLORS = ("#2563eb", "#ea580c", "#16a34a", "#9333ea", "#db2777", "#0891b2")
REASONS = {
    "return_reserve": "Недостаточно энергии для действия и возврата с резервом",
    "invalid_move": "Между вершинами нет ребра",
    "vertex_capacity": "В одной вершине оказались больше двух роботов",
    "transfer_required": "Общая вершина разрешена только при передаче груза",
    "transfer_location": "Для передачи роботы должны встретиться в одной вершине",
    "handoff_required": "До доставки нужна хотя бы одна передача другому роботу",
    "cargo_capacity": "Робот может нести только один груз",
    "edge_swap": "Встречный проезд по одному ребру запрещён",
    "pickup_location": "Робот находится вне точки погрузки",
    "delivery_location": "Груз находится вне точки доставки",
    "transfer_owner": "Передающий робот не владеет грузом",
    "receiver_loaded": "Получатель уже несёт груз. Для передачи нужен свободный робот",
    "transfer_participant": "Робот может участвовать только в одной передаче за такт",
    "transfer_busy": "Робот может участвовать только в одной передаче за такт",
    "unknown_node": "Вершины нет в графе",
}


def event_message(event):
    task = event.get("task_label") or event.get("task")
    if task and task != event.get("task"):
        task = f"{task.partition(':')[0]} ({event['task']})"
    if event["type"] == "transfer":
        return f"{event['from']} передал груз {task} роботу {event['to']}"
    if event["type"] == "pickup":
        return f"{event['robot']} забрал груз {task}"
    if event["type"] == "delivery":
        goal = event.get("dropoff_label")
        return f"Груз {task} доставлен" + (f": {goal}" if goal else "")
    if event["type"] == "rejected":
        return REASONS.get(event.get("code"), event["message"])
    if event["type"] == "wait":
        return f"{event['robot']} ожидает: {event.get('to_label', event['to'])}"
    if event["type"] == "move":
        return f"{event['robot']}: {event.get('from_label', event['from'])} → {event.get('to_label', event['to'])}"
    return event.get("message", event["type"])


def robot_rows(frame):
    return [{"Робот": r["id"], "Вершина": r.get("position_label", r["position"]),
             "Груз": r.get("cargo_label") or r["cargo"] or "Свободен",
             "Следующая цель": r.get("destination_label", ""),
             "Энергия": round(r["battery"], 3), "Заряд, %": round(100 * r["battery"] / r["capacity"], 1),
             "Расход за ребро": r["move_cost"], "Станция": r.get("station_label", r["station"]),
             "Резерв до станции": round(r["return_required"] + r["reserve"], 3)}
            for r in frame["robots"]]


def task_rows(frame):
    statuses = {"pending": "Ожидает погрузки", "carried": "В пути", "delivered": "Доставлен"}
    return [{"Груз": task.get("label") or task["id"],
             "Откуда забрать": task.get("pickup_label", task["pickup"]),
             "Куда доставить": task.get("dropoff_label", task["dropoff"]),
             "Несёт": task["owner"] or "", "Статус": statuses[task["status"]],
             "Передача выполнена": "Да" if task["handed"] else "Нет"}
            for task in frame["tasks"]]


def draw_graph(scenario, frame):
    nodes = {n["id"]: (n["x"], n["y"]) for n in scenario["nodes"]}
    labels = {n["id"]: n.get("label") or n["id"] for n in scenario["nodes"]}
    stations = {r["station"] for r in scenario["robots"]}
    dense = len(nodes) > 64
    landmarks = stations | {t[k] for t in scenario["tasks"] for k in ("pickup", "dropoff")}
    figure, axis = plt.subplots(figsize=(10, 7 if dense else 4.8))
    figure.patch.set_facecolor("#f8fafc")
    axis.set_facecolor("#f8fafc")
    for edge in scenario["edges"]:
        a, b = nodes[edge["source"]], nodes[edge["target"]]
        axis.plot((a[0], b[0]), (a[1], b[1]), color="#cbd5e1", linewidth=1 if dense else 3, zorder=1)
        if edge.get("cost", 1) != 1:
            axis.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + .08,
                      str(edge["cost"]), fontsize=9, color="#64748b")
    for nid, (x, y) in nodes.items():
        axis.scatter(x, y, marker="s" if nid in stations else "o",
                     s=450 if nid in stations else 15 if dense else 170,
                     color="#dcfce7" if nid in stations else "#e2e8f0", edgecolors="#94a3b8", zorder=2)
        if not dense or nid in landmarks:
            axis.text(x, y - .45 if dense else y - .28,
                      labels[nid] + (" [S]" if nid in stations else ""),
                      ha="center", fontsize=7 if dense else 9, color="#475569")
    by_node = defaultdict(list)
    for index, robot in enumerate(frame["robots"]):
        by_node[robot["position"]].append((index, robot))
    for nid, occupants in by_node.items():
        x, y = nodes[nid]
        for offset, (index, robot) in enumerate(occupants):
            dx = (offset - (len(occupants) - 1) / 2) * .38
            axis.scatter(x + dx, y + .08, s=440, color=COLORS[index % len(COLORS)],
                         edgecolors="white", linewidth=1.5, zorder=4)
            axis.text(x + dx, y + .08, robot["id"], color="white", ha="center", va="center",
                      weight="bold", fontsize=9, zorder=5)
            if robot["cargo"]:
                axis.text(x + dx, y + .38, f"[{robot['cargo']}]", ha="center",
                          color=COLORS[index % len(COLORS)], weight="bold", fontsize=10)
    parcels = defaultdict(list)
    for task in frame["tasks"]:
        if task["status"] != "carried":
            node = task["dropoff"] if task["status"] == "delivered" else task["pickup"]
            parcels[node, task["status"]].append(task["id"])
    for (node, status), tasks in parcels.items():
        x, y = nodes[node]
        label = tasks[0] + (f" +{len(tasks) - 1}" if len(tasks) > 1 else "")
        axis.text(x, y + .63, f"{label} {'✓' if status == 'delivered' else '□'}",
                  color="#15803d" if status == "delivered" else "#475569", ha="center")
    axis.set_title(f"Такт {frame['timestep']}", loc="left", fontsize=13)
    axis.set_aspect("equal", adjustable="datalim")
    axis.margins(x=.12, y=.12 if dense else .6)
    axis.axis("off")
    figure.tight_layout()
    return figure
