import copy
import json
import unittest
from pathlib import Path
from recursa.engine import run_smoke, validate_spec


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(Path("examples/specs/tasks.json").read_text())

    def test_smoke_is_honest_and_exportable(self):
        run = run_smoke(self.spec)
        self.assertEqual(run["metrics"]["model_calls"], 0)
        self.assertIsNone(run["metrics"]["functional_success"])
        self.assertEqual(json.loads(run["artifacts"][0]["content"])["requirement_order"][0], "TASK-01")

    def test_cycles_unknown_ids_duplicates(self):
        for mutation in ("cycle", "unknown", "duplicate"):
            spec = copy.deepcopy(self.spec)
            if mutation == "cycle":
                spec["requirements"][0]["depends_on"] = ["TASK-05"]
            elif mutation == "unknown":
                spec["requirements"][0]["depends_on"] = ["MISSING"]
            else:
                spec["requirements"][1]["id"] = "TASK-01"
            with self.assertRaises(ValueError):
                validate_spec(spec)
