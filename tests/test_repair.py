from pathlib import Path
import shutil
import tempfile
import unittest

from recursa.experiments import ROOT
from recursa.repair import repair_artifacts
from recursa.verification import check_sources


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.artifacts = [{"path": "app.js", "content": "const = ;", "requirements": ["R1"]},
                          {"path": "other.js", "content": "const untouched = true;", "requirements": ["R2"]}]
        self.failure = {"status": "syntax-failed", "checks": [{"path": "app.js", "kind": "javascript-syntax", "status": "failed", "diagnostic": "Unexpected token"}], "functional_success": None}

    def invoke(self, callback, verify, **options):
        return repair_artifacts(self.artifacts, {"R1", "R2"}, self.failure, callback, verify, **options)

    def replacement(self, content="const repaired = true;", path="app.js", requirements=None):
        return {"artifacts": [{"path": path, "content": content, "requirements": requirements or ["R1"]}]}

    @unittest.skipUnless(shutil.which("node"), "Node needed for real non-executing repair verification")
    def test_repairs_only_implicated_source_with_actual_parser(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        contexts = []
        def callback(context):
            contexts.append(context)
            return self.replacement()
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            result = self.invoke(callback, check_sources, output_dir=tmp)
            self.assertEqual(result["status"], "rechecked")
            self.assertEqual(result["verification"]["status"], "syntax-passed")
            self.assertIsNone(result["verification"]["functional_success"])
            self.assertEqual(result["artifacts"][1]["content"], self.artifacts[1]["content"])
            self.assertEqual(contexts[0]["allowed_paths"], ["app.js"])
            self.assertTrue((Path(tmp) / "repair-state.json").exists())
            self.assertTrue((Path(tmp) / "private/repair-context-001.json").exists())

    def test_attempt_limit_and_noop_stop(self):
        calls = []
        zero = self.invoke(lambda c: calls.append(c), lambda a: self.failure, max_attempts=0)
        self.assertEqual(zero["status"], "attempt-limit")
        self.assertFalse(calls)
        noop = self.invoke(lambda c: self.replacement("const = ;"), lambda a: self.failure)
        self.assertEqual(noop["status"], "no-op")
        self.assertEqual(len(noop["attempts"]), 1)
        count = 0
        def still_wrong(context):
            nonlocal count
            count += 1
            return self.replacement("const = " + str(count) + ";")
        exhausted = self.invoke(still_wrong, lambda a: self.failure, max_attempts=2)
        self.assertEqual(exhausted["status"], "attempt-limit")
        self.assertEqual(count, 2)

    def test_allowlist_and_provenance_cannot_expand(self):
        for output in (self.replacement(path="other.js", requirements=["R2"]),
                       self.replacement(requirements=["R2"]), self.replacement(path="../escape.js")):
            result = self.invoke(lambda c: output, lambda a: self.failure)
            self.assertEqual(result["status"], "invalid-output")
            self.assertEqual(result["artifacts"][0]["content"], "const = ;")

    def test_unknown_verification_keeps_last_measured_source(self):
        result = self.invoke(lambda c: self.replacement(), lambda a: {"status": "not-checked", "checks": []})
        self.assertEqual(result["status"], "verification-incomplete")
        self.assertEqual(result["artifacts"][0]["content"], "const = ;")
        def broken_verifier(_):
            raise RuntimeError("private diagnostics")
        result = self.invoke(lambda c: self.replacement(), broken_verifier)
        self.assertEqual(result["status"], "verification-error")
        self.assertNotIn("private diagnostics", str(result["attempts"]))

    def test_context_budget_and_callback_failure_stop_safely(self):
        artifacts = [dict(self.artifacts[0], content="x" * 4000)]
        result = repair_artifacts(artifacts, {"R1"}, self.failure, lambda c: self.fail("must not call"), lambda a: self.failure, max_context_chars=1024)
        self.assertEqual(result["status"], "context-too-large")
        def broken_callback(_):
            raise RuntimeError("private failure")
        result = self.invoke(broken_callback, lambda a: self.failure)
        self.assertEqual(result["status"], "callback-failed")
        self.assertNotIn("private failure", str(result["attempts"]))
