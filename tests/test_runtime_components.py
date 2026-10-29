import copy
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from recursa.artifacts import validate_artifacts
from recursa.budget import BudgetExceeded, CallBudget
from recursa.context import ContextIndex
from recursa.engine import validate_spec


def limits():
    return {"max_calls": 2, "max_output_tokens": 2048, "max_input_bytes": 100000,
            "max_wall_seconds": 30, "max_cost_usd": 0.1, "max_depth": 1,
            "max_concurrency": 1, "max_repairs": 0}


class RuntimeComponentsTests(unittest.TestCase):
    def test_sections_hierarchy_contracts_and_metadata_pagination(self):
        spec = {"sections": [{"id": "SEC-1", "text": "Task workflows"}],
                "sources": [{"id": "SRC-1", "title": "Owner specification"}],
                "schemas": {"Task": {"type": "object", "properties": {"title": {"type": "string"}}}},
                "design": {"primary": "cyan"},
                "requirements": [{"id": f"R{i}", "text": f"Requirement {i}", "section_id": "SEC-1",
                                  "source_refs": ["SRC-1"], "acceptance": ["Observable criterion"]} for i in range(40)]}
        spec["requirements"][1].update(parent_id="R0", cross_references=["SEC-1", "R0"])
        events = []
        index = ContextIndex(spec, lambda *event: events.append(event))
        self.assertEqual(index.metadata()["next_offset"], 32)
        self.assertEqual(len(index.metadata(offset=32)["requirement_ids"]), 8)
        self.assertEqual(index.read_section("SEC-1")["text"], "Task workflows")
        self.assertEqual(index.read_schema("Task")["type"], "object")
        self.assertEqual(len(events), 2)
        invalid = copy.deepcopy(spec)
        invalid["requirements"][0]["parent_id"] = "R1"
        with self.assertRaises(ValueError):
            validate_spec(invalid)
        invalid = copy.deepcopy(spec)
        invalid["requirements"][0]["source_refs"] = ["unknown"]
        with self.assertRaises(ValueError):
            validate_spec(invalid)

    def test_context_reads_are_bounded_and_observed(self):
        events = []
        spec = {"requirements": [{"id": "R1", "text": "Search task titles"}, {"id": "R2", "text": "Persist tasks"}]}
        index = ContextIndex(spec, lambda *e: events.append(e))
        rows = index.read(["R1"])
        rows[0]["text"] = "mutation"
        self.assertEqual(index.read(["R1"])[0]["text"], "Search task titles")
        self.assertEqual(index.search("Persist")[0]["id"], "R2")
        self.assertEqual(len(events), 3)
        with self.assertRaises(ValueError):
            ContextIndex(spec, max_chars=5).read(["R1"])
        with self.assertRaises(KeyError):
            index.read(["unknown"])

    def test_budget_reserves_failed_attempts_and_denies_unknown_models(self):
        budget = CallBudget(limits(), {"m": {"input_per_million": 1, "output_per_million": 1}})
        for _ in range(2):
            budget.reserve("m", "hi", 1024)
        with self.assertRaises(BudgetExceeded):
            budget.reserve("m", "hi", 1)
        with self.assertRaises(BudgetExceeded):
            budget.reserve("unknown", "hi", 1)
        self.assertEqual(budget.calls, 2)
        self.assertGreater(budget.cost_reserved, 0)

    def test_cost_reservation_prevents_dispatch(self):
        budget = CallBudget(dict(limits(), max_cost_usd=0), {"m": {"input_per_million": 1, "output_per_million": 1}})
        with self.assertRaises(BudgetExceeded):
            budget.reserve("m", "hi", 1)
        self.assertEqual(budget.calls, 0)

    def test_concurrent_reservations_never_exceed_the_cap(self):
        budget = CallBudget(limits(), {"m": {"input_per_million": 0, "output_per_million": 0}})
        def attempt(_):
            try:
                budget.reserve("m", "hi", 1)
                return True
            except BudgetExceeded:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(20)))
        self.assertEqual(sum(results), 2)
        self.assertEqual(budget.calls, 2)

    def test_wall_time_and_output_limits_fail_before_reserving(self):
        for setting in ("wall", "output", "input"):
            budget = CallBudget(limits(), {"m": {"input_per_million": 0, "output_per_million": 0}})
            if setting == "wall":
                budget.started -= 100
            elif setting == "output":
                budget.limits["max_output_tokens"] = 1
            else:
                budget.limits["max_input_bytes"] = 1
            with self.subTest(setting=setting), self.assertRaises(BudgetExceeded):
                budget.reserve("m", "hello", 2)
            self.assertEqual(budget.calls, 0)

    def test_malformed_requirements_and_artifacts_rejected(self):
        for bad in (None, ["not an object"], [{"id": "R1", "text": "ok", "depends_on": [[]]}]):
            with self.assertRaises(ValueError):
                validate_spec({"requirements": bad})
        for bad in ([None], [{"path": "src/app.ts", "content": "", "requirements": [[]]}]):
            with self.assertRaises(ValueError):
                validate_artifacts({"artifacts": bad}, {"R1"})

    def test_artifact_protocol_and_path_attacks(self):
        valid = {"path": "src/app.ts", "content": "export const task = 1;", "requirements": ["R1"]}
        result = validate_artifacts({"artifacts": [valid]}, {"R1"})
        self.assertEqual(len(result[0]["sha256"]), 64)
        for path in ("../escape.ts", "/absolute.ts", "C:/escape.ts", "src\\evil.ts", ".env", "src/../evil.ts", "src/CON.ts", "src/file.ts."):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_artifacts({"artifacts": [dict(valid, path=path)]}, {"R1"})
        with self.assertRaises(ValueError):
            validate_artifacts({"artifacts": [valid, dict(valid, path="SRC/APP.ts")]}, {"R1"})
        with self.assertRaises(ValueError):
            validate_artifacts({"artifacts": [dict(valid, requirements=["invented"])]}, {"R1"})
