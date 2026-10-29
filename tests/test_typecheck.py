from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from recursa.experiments import ROOT
from recursa.typecheck import check_types
from recursa.verification import check_sources

COMPILER = ROOT / "tooling/typecheck/node_modules/typescript"


class TypecheckTests(unittest.TestCase):
    def fixture(self, content):
        return [{"path": "src/task.ts", "content": content, "requirements": ["R1"]}]

    def test_missing_compiler_is_not_success(self):
        result = check_types(self.fixture("const v: number = 1;"), ROOT / "compiler-not-installed")
        self.assertIsNone(result["typecheck_success"])
        self.assertEqual(result["status"], "unavailable")

    @unittest.skipUnless(COMPILER.exists() and shutil.which("node"), "Install tooling/typecheck locked dependencies for actual compiler tests")
    def test_actual_compiler_accepts_contract_and_rejects_type_error(self):
        scratch = ROOT / ".cache/typecheck"
        valid = check_types(self.fixture('export interface Task { title: string }; const task: Task = {title: "ok"};'), COMPILER, scratch_directory=scratch)
        self.assertTrue(valid["typecheck_success"], valid)
        invalid = check_types(self.fixture('const count: number = "wrong";'), COMPILER, scratch_directory=scratch)
        self.assertFalse(invalid["typecheck_success"])
        self.assertIn("TS2322", invalid["checks"][0]["diagnostic"])
        self.assertIsNone(valid["functional_success"])
        combined = check_sources(self.fixture('const count: number = "wrong";'), typescript_directory=COMPILER, scratch_directory=scratch)
        self.assertEqual(combined["status"], "static-failed")
        self.assertFalse(combined["typecheck_success"])

    @unittest.skipUnless(COMPILER.exists() and shutil.which("node"), "Install tooling/typecheck locked dependencies for actual compiler tests")
    def test_generated_source_is_never_executed_and_deadlines_are_failures(self):
        scratch = ROOT / ".cache/typecheck"
        source = 'throw new Error("MUST_NOT_EXECUTE"); export const v: number = 1;'
        result = check_types(self.fixture(source), COMPILER, scratch_directory=scratch)
        self.assertTrue(result["typecheck_success"], result)
        with patch("recursa.typecheck.subprocess.run", side_effect=subprocess.TimeoutExpired("tsc", 1)):
            result = check_types(self.fixture(source), COMPILER, scratch_directory=scratch)
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(result["typecheck_success"])
