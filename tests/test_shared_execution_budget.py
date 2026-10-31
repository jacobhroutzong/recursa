import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recursa.budget import Deadline, BudgetExceeded, CallBudget
from recursa.offline import fixture
from recursa.pipeline import verify_application


class SharedDeadlineTests(unittest.TestCase):
    def test_remaining_budget_is_sticky_and_caps_stage_duration(self):
        with patch('recursa.budget.time.monotonic', return_value=10):
            deadline = Deadline(5)
        with patch('recursa.budget.time.monotonic', return_value=13):
            self.assertEqual(deadline.remaining(30), 2)
        with patch('recursa.budget.time.monotonic', return_value=16):
            with self.assertRaises(BudgetExceeded):
                deadline.remaining()
        with patch('recursa.budget.time.monotonic', return_value=10):
            with self.assertRaises(BudgetExceeded):
                deadline.remaining()

    def test_expiration_stops_next_stage_and_preserves_measured_output(self):
        spec, artifacts, _ = fixture()
        deadline = Deadline(10)
        def static(*args, **kwargs):
            self.assertLessEqual(kwargs['max_seconds'], 10)
            deadline.started -= 20
            return {'checks': [], 'status': 'not-checked', 'typecheck_success': None}
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.pipeline.check_sources', side_effect=static), patch('recursa.pipeline.lint_sources') as lint:
            with self.assertRaises(BudgetExceeded):
                verify_application(spec, artifacts, tmp, deadline=deadline)
            lint.assert_not_called()
            self.assertTrue(Path(tmp, 'verification-000/source.json').exists())
            self.assertTrue(Path(tmp, 'artifacts/src/main.ts').exists())
            self.assertEqual(json.loads(Path(tmp, 'application-report.json').read_text())['status'], 'budget-exhausted')

    def test_repair_budget_count_is_bounded(self):
        limits = {'max_calls': 2, 'max_output_tokens': 10, 'max_input_bytes': 1000,
                  'max_wall_seconds': 5, 'max_cost_usd': 0, 'max_depth': 1,
                  'max_concurrency': 1, 'max_repairs': 1}
        budget = CallBudget(limits, {'m': {'input_per_million': 0, 'output_per_million': 0}})
        self.assertGreater(budget.remaining(), 0)
        for count in (True, -1, 11):
            with self.assertRaises(ValueError):
                CallBudget(dict(limits, max_repairs=count), budget.rates)
