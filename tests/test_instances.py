import copy
import json
from pathlib import Path
import tempfile
import unittest

from instances import create_instance, fingerprint, load_instance, save_instance, solver_inputs


class InstanceTests(unittest.TestCase):
    def make(self, **kwargs):
        options = dict(n=12, m=16, num_tasks=4, num_robots=3, battery=80)
        return create_instance(**(options | kwargs))

    def test_seeded_placements_use_only_walkable_vertices(self):
        first = self.make(geometry_seed=7, placement_seed=9)
        self.assertEqual(first, self.make(geometry_seed=7, placement_seed=9))
        other = self.make(geometry_seed=7, placement_seed=10)
        self.assertEqual(first['edges'], other['edges'])
        self.assertEqual(first['cells'], other['cells'])
        self.assertNotEqual(first['tasks'], other['tasks'])
        vertices = set(range(first['num_vertices']))
        self.assertEqual(len(first['coords']), len(vertices))
        self.assertEqual(len({r['start_vertex'] for r in first['robots']}), 3)
        for robot in first['robots']:
            self.assertIn(robot['start_vertex'], vertices)
        for task in first['tasks']:
            self.assertIn(task['start_vertex'], vertices)
            self.assertIn(task['finish_vertex'], vertices)
            self.assertNotEqual(task['start_vertex'], task['finish_vertex'])

    def test_round_trip_and_checksum_detect_tampering(self):
        instance = self.make()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'instance.json'
            self.assertEqual(save_instance(instance, path), fingerprint(instance))
            self.assertEqual(load_instance(path), instance)
            with self.assertRaises(FileExistsError):
                save_instance(instance, path)
            saved = json.loads(path.read_text(encoding='utf-8'))
            saved['instance']['robots'][0]['battery'] += 1
            path.write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'checksum|SHA|контроль'):
                load_instance(path)

    def test_solver_inputs_are_independent(self):
        instance = self.make()
        before = copy.deepcopy(instance)
        first = solver_inputs(instance)
        second = solver_inputs(instance)
        self.assertEqual(first, second)
        first[1].clear()
        first[2].clear()
        first[3].clear()
        self.assertEqual(instance, before)
        self.assertTrue(second[1])
        self.assertEqual(len(second[2]), 3)
        self.assertEqual(len(second[3]), 4)

    def test_invalid_load_is_rejected(self):
        for value in (-1, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.make(num_robots=value)
        with self.assertRaises(ValueError):
            create_instance(n=2, m=2, num_robots=5)
        with self.assertRaises(ValueError):
            self.make(battery=-1)
        with self.assertRaises(ValueError):
            self.make(num_tasks=-1)

    def test_zero_tasks_and_smallest_map(self):
        instance = create_instance(n=2, m=2, num_tasks=0, num_robots=1)
        self.assertEqual(instance['tasks'], [])
        self.assertEqual(len(instance['robots']), 1)


if __name__ == '__main__':
    unittest.main()
