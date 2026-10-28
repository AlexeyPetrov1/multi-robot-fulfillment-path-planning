"""Проходимые клетки склада: длинные проходы, поперечные проходы и четыре зоны."""

import random
from dataclasses import dataclass


@dataclass
class WarehouseMap:
    config: dict
    graph: dict
    cells: list
    zones: list
    passages: list

    @property
    def coords(self):
        return [[c / max(1, self.config["m"] - 1), r / max(1, self.config["n"] - 1)]
                for r, c in self.cells]


def generate_warehouse(n=15, m=20, topology="long_aisles", aisle_width=1,
                       rack_width=2, rack_count=None, rack_length=None,
                       cross_aisles=2, cross_positions=None, passage_width=1,
                       passage_positions=None, split_row=None, split_col=None, seed=42):
    """Размеры заданы в клетках; явные позиции проходов задаются в координатах сетки.

    rack_count/rack_length относятся к каждому блоку стеллажей (к каждой зоне).
    cross_positions задаёт начала горизонтальных полос ширины aisle_width.
    passage_positions содержит три координаты вдоль границ в порядке passages.
    """
    def integer(value, name, minimum=1):
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            raise ValueError(f"{name}: требуется целое число не меньше {minimum}")

    for name, value in (("n", n), ("m", m), ("aisle_width", aisle_width),
                        ("rack_width", rack_width), ("passage_width", passage_width)):
        integer(value, name)
    integer(cross_aisles, "cross_aisles", 0)
    if rack_count is not None:
        integer(rack_count, "rack_count", 0)
    if rack_length is not None:
        integer(rack_length, "rack_length")
    if topology not in ("long_aisles", "cross_aisles", "zoned"):
        raise ValueError("Неизвестная топология склада")
    if aisle_width > min(n, m) or rack_width > m:
        raise ValueError("Ширины не помещаются в сетку")
    if topology != "cross_aisles" and cross_positions:
        raise ValueError("cross_positions используются только в cross_aisles")
    if topology != "zoned" and (passage_positions is not None
                                or split_row is not None or split_col is not None):
        raise ValueError("Параметры зон используются только в zoned")

    config = dict(n=n, m=m, topology=topology, aisle_width=aisle_width,
                  rack_width=rack_width, rack_count=rack_count, rack_length=rack_length,
                  cross_aisles=cross_aisles, cross_positions=cross_positions,
                  passage_width=passage_width, passage_positions=passage_positions,
                  split_row=split_row, split_col=split_col, seed=seed)
    walk, passages = {}, []

    def room(top, left, height, width, zone, crosses=False):
        if aisle_width > min(height, width):
            raise ValueError("Ширина прохода не помещается в зоне")
        maximum = max(0, (width - aisle_width) // (rack_width + aisle_width))
        length_limit = max(0, height - 2 * aisle_width)
        count = rack_count if rack_count is not None else (maximum if length_limit else 0)
        length = rack_length if rack_length is not None else length_limit
        if count > maximum or length > length_limit or (count and not length):
            raise ValueError("Стеллажи не помещаются между торцевыми проходами")
        walk.update({(r, c): zone for r in range(top, top + height)
                     for c in range(left, left + width)})
        first_row = top + (height - length) // 2
        for index in range(count):
            first_col = left + aisle_width + index * (rack_width + aisle_width)
            for r in range(first_row, first_row + length):
                for c in range(first_col, first_col + rack_width):
                    del walk[r, c]
        if not crosses:
            return
        if cross_positions is None:
            positions = []
            if count and cross_aisles:
                free = length - cross_aisles * aisle_width
                if free < cross_aisles + 1:
                    raise ValueError("Поперечные проходы не помещаются внутри стеллажей")
                cursor = first_row
                for index in range(cross_aisles):
                    cursor += ((index + 1) * free // (cross_aisles + 1)
                               - index * free // (cross_aisles + 1))
                    positions.append(cursor)
                    cursor += aisle_width
        else:
            positions = list(cross_positions)
        for pos in positions:
            integer(pos, "cross_positions", 0)
            if not count or not first_row < pos or pos + aisle_width >= first_row + length:
                raise ValueError("Поперечный проход должен находиться внутри стеллажей")
        positions.sort()
        if any(b - a <= aisle_width for a, b in zip(positions, positions[1:])):
            raise ValueError("Поперечные проходы перекрываются или сливаются")
        for pos in positions:
            walk.update({(r, c): zone for r in range(pos, pos + aisle_width)
                         for c in range(left, left + width)})
        config.update(cross_positions=positions, cross_aisles=len(positions))

    if topology != "zoned":
        room(0, 0, n, m, 0, topology == "cross_aisles")
    else:
        row = n // 2 if split_row is None else split_row
        col = m // 2 if split_col is None else split_col
        integer(row, "split_row")
        integer(col, "split_col")
        if row >= n - 1 or col >= m - 1:
            raise ValueError("Разделители должны оставлять четыре непустые зоны")
        config.update(split_row=row, split_col=col)
        room(0, 0, row, col, 0)
        room(0, col + 1, row, m - col - 1, 1)
        room(row + 1, 0, n - row - 1, col, 2)
        room(row + 1, col + 1, n - row - 1, m - col - 1, 3)
        boundaries = [((0, 1), "row", 0, row), ((0, 2), "col", 0, col),
                      ((1, 3), "col", col + 1, m), ((2, 3), "row", row + 1, n)]
        rng = random.Random(seed)
        del boundaries[rng.randrange(4)]
        if passage_positions is not None and len(passage_positions) != 3:
            raise ValueError("Для трёх соединений нужны три позиции")
        resolved = []
        for index, (pair, axis, lo, hi) in enumerate(boundaries):
            if passage_width > hi - lo:
                raise ValueError("Межзональный проход не помещается на границе")
            position = (rng.randint(lo, hi - passage_width) if passage_positions is None
                        else passage_positions[index])
            integer(position, "passage_positions", 0)
            if not lo <= position <= hi - passage_width:
                raise ValueError("Позиция межзонального прохода вне границы зон")
            cells = [(p, col) if axis == "row" else (row, p)
                     for p in range(position, position + passage_width)]
            walk.update({cell: pair[0] for cell in cells})
            passages.append(dict(zones=list(pair), cells=[list(cell) for cell in cells],
                                 width=passage_width, axis=axis, position=position))
            resolved.append(position)
        config["passage_positions"] = resolved

    cells = sorted(walk)
    ids = {cell: vertex for vertex, cell in enumerate(cells)}
    graph = {}
    for vertex, (r, c) in enumerate(cells):
        graph[vertex] = sorted((ids[cell], 1) for cell in
                               ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
                               if cell in ids)
    return WarehouseMap(config, graph, cells, [walk[cell] for cell in cells], passages)
