import time
import unittest
from collections import deque

from warehouse import WarehouseMap, generate_warehouse


def reached(graph, start=0, removed=()):
    removed = set(removed)
    found, queue = {start}, deque([start])
    while queue:
        for other, _ in graph[queue.popleft()]:
            if other not in found and other not in removed:
                found.add(other)
                queue.append(other)
    return found


class WarehouseTests(unittest.TestCase):
    def check_map(self, layout, n, m):
        self.assertIsInstance(layout, WarehouseMap)
        self.assertEqual(set(layout.graph), set(range(len(layout.cells))))
        self.assertEqual(len(layout.cells), len(set(layout.cells)))
        self.assertEqual(len(layout.zones), len(layout.cells))
        self.assertEqual(len(reached(layout.graph)), len(layout.cells))
        self.assertEqual(len(layout.coords), len(layout.cells))
        for vertex, (row, col) in enumerate(layout.cells):
            self.assertTrue(0 <= row < n and 0 <= col < m)
            self.assertEqual(layout.coords[vertex], [col / max(1, m - 1), row / max(1, n - 1)])
            for other, weight in layout.graph[vertex]:
                r2, c2 = layout.cells[other]
                self.assertEqual(abs(row - r2) + abs(col - c2), 1)
                self.assertEqual(weight, 1)
                self.assertIn((vertex, 1), layout.graph[other])

    def test_long_aisles_have_real_racks_and_only_two_end_connections(self):
        layout = generate_warehouse(15, 20)
        self.check_map(layout, 15, 20)
        self.assertLess(len(layout.cells), 15 * 20)
        self.assertEqual(set(layout.zones), {0})
        self.assertEqual(layout.passages, [])
        cells = set(layout.cells)
        self.assertNotIn((7, 1), cells)
        self.assertNotIn((7, 2), cells)
        horizontal = {r for r in range(15) if all((r, c) in cells for c in range(4))}
        self.assertEqual(horizontal, {0, 14})
        # Removing the two connecting ends separates the parallel aisles.
        graph = {v: [(u, w) for u, w in ns if layout.cells[u][0] not in (0, 14)]
                 for v, ns in layout.graph.items() if layout.cells[v][0] not in (0, 14)}
        self.assertLess(len(reached(graph, next(iter(graph)))), len(graph))

    def test_explicit_rack_dimensions_and_count(self):
        layout = generate_warehouse(13, 17, aisle_width=2, rack_width=3,
                                    rack_count=2, rack_length=7)
        self.check_map(layout, 13, 17)
        self.assertEqual(13 * 17 - len(layout.cells), 2 * 3 * 7)

    def test_cross_aisles_open_only_the_requested_internal_rows(self):
        layout = generate_warehouse(15, 20, topology="cross_aisles",
                                    cross_positions=[4, 9])
        self.check_map(layout, 15, 20)
        cells = set(layout.cells)
        self.assertTrue(all((r, c) in cells for r in (4, 9) for c in range(20)))
        self.assertNotIn((5, 1), cells)
        self.assertNotIn((8, 2), cells)
        self.assertEqual({r for r in range(15) if all((r, c) in cells for c in range(4))},
                         {0, 4, 9, 14})

    def test_automatic_cross_aisles_have_the_requested_count_and_width(self):
        layout = generate_warehouse(21, 24, topology="cross_aisles", aisle_width=2,
                                    cross_aisles=3)
        cells = set(layout.cells)
        internal = [r for r in range(2, 19) if all((r, c) in cells for c in range(24))]
        self.assertEqual(len(internal), 6)

    def test_four_zones_have_exactly_three_narrow_connections_forming_a_tree(self):
        layout = generate_warehouse(19, 23, topology="zoned", passage_width=1, seed=7)
        self.check_map(layout, 19, 23)
        self.assertEqual(set(layout.zones), {0, 1, 2, 3})
        self.assertEqual(len(layout.passages), 3)
        pairs = set()
        cross_edges = []
        for v, neighbors in layout.graph.items():
            for u, _ in neighbors:
                if v < u and layout.zones[v] != layout.zones[u]:
                    pairs.add(tuple(sorted((layout.zones[v], layout.zones[u]))))
                    cross_edges.append((v, u))
        self.assertEqual(len(pairs), 3)
        self.assertEqual(len(cross_edges), 3)
        self.assertEqual(pairs, {tuple(sorted(p["zones"])) for p in layout.passages})
        for passage in layout.passages:
            ids = [layout.cells.index(tuple(cell)) for cell in passage["cells"]]
            self.assertEqual(len(ids), 1)
            remaining = set(layout.graph) - set(ids)
            self.assertLess(len(reached(layout.graph, min(remaining), ids)), len(remaining))

    def test_wider_passages_and_custom_splits(self):
        layout = generate_warehouse(23, 27, topology="zoned", passage_width=2,
                                    split_row=9, split_col=11, seed=5)
        self.check_map(layout, 23, 27)
        self.assertEqual(layout.config["split_row"], 9)
        self.assertEqual(layout.config["split_col"], 11)
        self.assertTrue(all(len(p["cells"]) == 2 for p in layout.passages))
        positions = [p["cells"][0][0] if p["cells"][0][1] == 11
                     else p["cells"][0][1] for p in layout.passages]
        repeated = generate_warehouse(23, 27, topology="zoned", passage_width=2,
                                      split_row=9, split_col=11, seed=5,
                                      passage_positions=positions)
        self.assertEqual(layout.cells, repeated.cells)
        self.assertEqual(layout.passages, repeated.passages)

    def test_seed_reproduces_geometry_and_config_preserves_every_parameter(self):
        first = generate_warehouse(19, 23, topology="zoned", seed=11)
        second = generate_warehouse(19, 23, topology="zoned", seed=11)
        self.assertEqual(first, second)
        self.assertNotEqual(first.passages,
                            generate_warehouse(19, 23, topology="zoned", seed=12).passages)
        self.assertEqual(set(first.config), {
            "n", "m", "topology", "aisle_width", "rack_width", "rack_count", "rack_length",
            "cross_aisles", "cross_positions", "passage_width", "passage_positions",
            "split_row", "split_col", "seed",
        })

    def test_small_default_map_stays_walkable(self):
        layout = generate_warehouse(2, 2)
        self.check_map(layout, 2, 2)
        self.assertEqual(len(layout.cells), 4)

    def test_invalid_parameters_are_rejected(self):
        configs = [
            dict(n=0), dict(topology="unknown"), dict(aisle_width=0), dict(rack_width=-1),
            dict(rack_count=-1), dict(rack_count=100), dict(rack_length=100),
            dict(topology="cross_aisles", cross_aisles=-1),
            dict(topology="cross_aisles", cross_positions=[0]),
            dict(topology="cross_aisles", cross_positions=[4, 4]),
            dict(topology="zoned", passage_width=0),
            dict(topology="zoned", passage_width=100),
            dict(topology="zoned", split_row=0),
            dict(topology="zoned", split_col=20),
            dict(topology="zoned", passage_positions=[1, 2]),
            dict(topology="zoned", passage_positions=[100, 100, 100]),
            dict(n=2, m=2, rack_count=1),
        ]
        for config in configs:
            with self.subTest(config=config), self.assertRaises(ValueError):
                generate_warehouse(**config)

    def test_128_square_generation_is_lightweight(self):
        started = time.perf_counter()
        for topology in ("long_aisles", "cross_aisles", "zoned"):
            layout = generate_warehouse(128, 128, topology=topology)
            self.assertLess(len(layout.cells), 128 * 128)
            self.assertEqual(len(reached(layout.graph)), len(layout.cells))
        self.assertLess(time.perf_counter() - started, 5)


if __name__ == "__main__":
    unittest.main()
