import copy
from pathlib import Path
import tempfile
import unittest

from recursa.experiments import ROOT
from recursa.taskgraph import TaskGraph


class TaskGraphTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.tmp.cleanup)
        self.graph = TaskGraph({"R1", "R2"}, Path(self.tmp.name))
        self.plan = [{"id": "contract", "label": "Task types", "kind": "contract", "requirements": ["R1"]},
                     {"id": "view", "label": "Task view", "kind": "view", "requirements": ["R2"], "depends_on": ["contract"]}]

    def produce_contract(self):
        self.graph.begin("contract")
        self.graph.submit("contract", {"artifacts": [{"path": "types.ts", "content": "export interface Task { title: string }", "requirements": ["R1"], "exports": ["Task"]}]})

    def test_dependency_order_persistence_and_contracts(self):
        self.graph.set_plan(self.plan)
        with self.assertRaises(ValueError):
            self.graph.begin("view")
        self.produce_contract()
        self.graph.begin("view")
        self.assertEqual(self.graph.contracts(["contract"])[0]["exports"], ["Task"])
        self.assertTrue((Path(self.tmp.name) / "intermediate/contract/types.ts").exists())
        self.assertEqual(self.graph.select_outputs(["types.ts"])[0]["requirements"], ["R1"])
        self.assertTrue((Path(self.tmp.name) / "task-graph.json").exists())

    def test_refinement_preserves_started_history(self):
        self.graph.set_plan(self.plan)
        self.produce_contract()
        refined = copy.deepcopy(self.plan)
        refined[1]["label"] = "Refined pending view"
        self.graph.set_plan(refined)
        self.assertEqual(self.graph.tasks["contract"]["status"], "produced")
        refined[0]["requirements"] = ["R2"]
        with self.assertRaises(ValueError):
            self.graph.set_plan(refined)

    def test_cycles_paths_overwrites_and_scope_rejected(self):
        cycle = copy.deepcopy(self.plan)
        cycle[0]["depends_on"] = ["view"]
        with self.assertRaises(ValueError):
            self.graph.set_plan(cycle)
        self.graph.set_plan(self.plan)
        self.graph.begin("contract")
        with self.assertRaises(ValueError):
            self.graph.submit("contract", {"artifacts": [{"path": "types.ts", "content": "x", "requirements": ["R2"]}]})
        self.assertEqual(self.graph.tasks["contract"]["status"], "running")
        with self.assertRaises(ValueError):
            self.graph.select_outputs(["unknown.ts"])
