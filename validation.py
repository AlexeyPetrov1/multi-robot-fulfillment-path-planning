"""Physical replay of a saved plan, independent of the planner and visualizer."""

from collections import Counter
from dataclasses import asdict, is_dataclass


def verify_result(instance, result):
    """Validate every tick; utilization covers ticks 1..last_delivery_tick.

    Busy means moving OR carrying cargo. Total moves cover the entire plan.
    Fractions are None when there are no robot-ticks to average.
    """
    try:
        return _replay(instance, asdict(result) if is_dataclass(result) else result)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError(f"Malformed instance or result: {error}") from error


def _replay(instance, result):
    assert result["success"] is True, "Result is not a successful plan"
    makespan = result["makespan"]
    assert type(makespan) is int and makespan >= 0, "Invalid makespan"
    limit = instance.get("config", {}).get("max_horizon")
    assert limit is None or makespan <= limit, "Plan exceeds max_horizon"
    assert all(type(t) is int or isinstance(t, str) and t.isdecimal()
               for t in result["ticks"]), "Invalid tick number"
    ticks = {int(t): rows for t, rows in result["ticks"].items()}
    assert len(ticks) == len(result["ticks"]), "Duplicate tick numbers"
    assert set(ticks) == set(range(1, makespan + 1)), "Missing or extra ticks"

    robots = {r["robot_id"]: r for r in instance["robots"]}
    tasks = {t["task_id"]: t for t in instance["tasks"]}
    assert len(robots) == len(instance["robots"]), "Duplicate robot IDs"
    assert len(tasks) == len(instance["tasks"]), "Duplicate task IDs"
    adjacency = {v: {v} for v in range(instance["num_vertices"])}
    for first, second in instance["edges"]:
        assert first in adjacency and second in adjacency, "Invalid graph edge"
        adjacency[first].add(second)
        adjacency[second].add(first)
    positions = {rid: r["start_vertex"] for rid, r in robots.items()}
    battery = {rid: r["battery"] for rid, r in robots.items()}
    cargo_at = {tid: t["start_vertex"] for tid, t in tasks.items()}
    goals = {tid: t["finish_vertex"] for tid, t in tasks.items()}
    assert all(type(v) is int and v in adjacency
               for v in (*positions.values(), *cargo_at.values(), *goals.values())), "Invalid initial vertex"
    assert all(type(b) is int and b >= 0 for b in battery.values()), "Invalid initial battery"
    maximum_occupancy = max(Counter(positions.values()).values(), default=0)
    assert maximum_occupancy <= 2, "Initial vertex capacity exceeded"
    delivered_at = {tid: 0 for tid in tasks if cargo_at[tid] == goals[tid]}
    previous = {tid: None for tid in tasks}
    moving, busy, handoffs = [0], [0], 0

    for tick in range(1, makespan + 1):
        rows = ticks[tick]
        assert all(len(row) == 4 for row in rows), f"Invalid row at tick {tick}"
        assert len(rows) == len(robots) and {row[0] for row in rows} == robots.keys(), f"Robot rows at tick {tick}"
        next_positions, carriers = {}, {}
        move_count = busy_count = 0
        for rid, vertex, cargo, reported_battery in rows:
            assert type(vertex) is int and vertex in adjacency[positions[rid]], f"Illegal move by robot {rid} at tick {tick}"
            moved = vertex != positions[rid]
            battery[rid] -= moved
            assert type(reported_battery) is int and reported_battery == battery[rid] >= 0, f"Battery of robot {rid} at tick {tick}"
            move_count += moved
            busy_count += moved or cargo is not None
            next_positions[rid] = vertex
            if cargo is not None:
                assert cargo in tasks and cargo not in carriers, f"Unknown or duplicate cargo at tick {tick}"
                assert cargo_at[cargo] == positions[rid], f"Cargo {cargo} pickup discontinuity at tick {tick}"
                donor = previous[cargo]
                if donor is not None and donor != rid:
                    assert positions[donor] == positions[rid], f"Cargo {cargo} transfer without meeting at tick {tick}"
                    handoffs += 1
                carriers[cargo] = rid

        for cargo, donor in previous.items():
            if donor is not None and cargo not in carriers:
                assert cargo_at[cargo] == goals[cargo], f"Cargo {cargo} dropped before delivery at tick {tick}"
        occupancy = max(Counter(next_positions.values()).values(), default=0)
        maximum_occupancy = max(maximum_occupancy, occupancy)
        assert occupancy <= 2, f"Vertex capacity exceeded at tick {tick}"
        for cargo, rid in carriers.items():
            vertex = next_positions[rid]
            if vertex != goals[cargo]:
                delivered_at.pop(cargo, None)
            elif cargo_at[cargo] != goals[cargo]:
                delivered_at[cargo] = tick
            cargo_at[cargo] = vertex
        previous = {cargo: carriers.get(cargo) for cargo in tasks}
        positions = next_positions
        moving.append(moving[-1] + move_count)
        busy.append(busy[-1] + busy_count)

    delivered = sum(cargo_at[tid] == goals[tid] for tid in tasks)
    assert delivered == len(tasks), f"Only {delivered}/{len(tasks)} tasks delivered"
    last = max(delivered_at.values(), default=0)
    denominator = len(robots) * last
    return dict(valid=True, delivered=delivered, last_delivery_tick=last, makespan=makespan,
                utilization=busy[last] / denominator if denominator else None,
                movement_utilization=moving[last] / denominator if denominator else None,
                busy_robot_ticks=busy[last], moving_robot_ticks=moving[last],
                robot_ticks_denominator=denominator, handoffs=handoffs,
                total_moves=moving[-1], max_vertex_occupancy=maximum_occupancy)
