import contextlib
import io
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from instances import load_instance
import visualize

ROOT = Path(__file__).resolve().parents[1]


class WarehouseIntegrationTests(unittest.TestCase):
    def test_generated_visualizer_uses_dense_walkable_cells(self):
        views = visualize.generated_warehouse(8, 12, 2, num_robots=2, battery=500,
                                             max_horizon=256, time_limit_s=6,
                                             topology='cross_aisles', planner='greedy',
                                             placement_seed=13)
        view = views[0]
        self.assertEqual(view['delivered'], 2)
        self.assertLess(view['n'], 96)
        self.assertEqual(view['warehouse']['topology'], 'cross_aisles')
        self.assertEqual(len(view['coords']), view['n'])
        cells = view['warehouse']['cells']
        for first, second, _ in view['edges']:
            a, b = cells[first], cells[second]
            self.assertEqual(abs(a[0]-b[0])+abs(a[1]-b[1]), 1)

    def test_solver_cli_saves_and_replays_identical_instance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'instance.json')
            options = ['test_run.py', '--planner', 'greedy', '--n', '8', '--m', '12',
                       '--tasks', '2', '--robots', '2', '--battery', '500', '--horizon', '256',
                       '--time-limit', '6', '--topology', 'cross_aisles',
                       '--geometry-seed', '7', '--placement-seed', '13', '--save-instance', path]
            with patch.object(sys, 'argv', options), patch('builtins.input', side_effect=AssertionError('interactive input')), contextlib.redirect_stdout(io.StringIO()) as output:
                runpy.run_path(str(ROOT / 'test_run.py'), run_name='__main__')
            self.assertNotIn('Решение не найдено', output.getvalue())
            saved = Path(path).read_bytes()
            instance = load_instance(path)
            self.assertEqual(instance['config']['geometry']['topology'], 'cross_aisles')
            self.assertEqual(instance['config']['placement_seed'], 13)
            with patch.object(sys, 'argv', ['test_run.py', '--planner', 'cp-sat', '--instance', path, '--horizon', '256', '--time-limit', '6']), patch('builtins.input', side_effect=AssertionError('interactive input')), contextlib.redirect_stdout(io.StringIO()) as output:
                runpy.run_path(str(ROOT / 'test_run.py'), run_name='__main__')
            self.assertNotIn('Решение не найдено', output.getvalue())
            self.assertEqual(Path(path).read_bytes(), saved)

    def test_visualizer_cli_exposes_geometry(self):
        with patch.object(sys, 'argv', ['visualize.py', '--help']), contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as stopped:
            runpy.run_path(str(ROOT / 'visualize.py'), run_name='__main__')
        self.assertEqual(stopped.exception.code, 0)
        for name in ('--topology', '--aisle-width', '--passage-width', '--placement-seed', '--instance'):
            self.assertIn(name, output.getvalue())

    def test_cp_failure_view_does_not_claim_global_optimality(self):
        views = visualize.generated_warehouse(2, 2, 1, num_robots=1, battery=20,
                                             max_horizon=10, time_limit_s=6,
                                             planner='cp-sat', failures=[{'p_fail': 0}])
        self.assertEqual(len(views), 2)
        self.assertTrue(all(not view['optimal'] for view in views))


if __name__ == '__main__':
    unittest.main()
