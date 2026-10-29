import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from recursa.experiments import ROOT
from recursa.verification import check_sources, declared_coverage


class SourceVerificationTests(unittest.TestCase):
    def test_declared_coverage_is_not_satisfaction(self):
        report = declared_coverage({"requirements": [{"id": "R1"}, {"id": "R2"}]},
                                   [{"path": "app.js", "requirements": ["R1"]}])
        self.assertEqual(report["unreferenced"], ["R2"])
        self.assertIsNone(report["satisfaction_rate"])

    @unittest.skipUnless(shutil.which("node"), "Node needed for real non-executing syntax check")
    def test_actual_syntax_check_never_executes_source(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            target = Path(tmp) / "MUST_NOT_EXIST"
            source = f'import fs from "node:fs"; fs.writeFileSync({json.dumps(str(target))}, "executed");'
            report = check_sources([{"path": "app.js", "content": source}])
            self.assertEqual(report["status"], "syntax-passed")
            self.assertFalse(target.exists())
            self.assertIsNone(report["functional_success"])
            invalid = check_sources([{"path": "app.js", "content": "const = ;"}])
            self.assertEqual(invalid["status"], "syntax-failed")

    @unittest.skipUnless(shutil.which("node"), "Node needed for inline-script syntax check")
    def test_html_inline_json_and_external_scripts(self):
        report = check_sources([{"path": "index.html", "content": '<script type="application/json">{"ok":true}</script><script type="module">export const = 2;</script><script src="https://example.invalid/script.js"></script>'}])
        self.assertEqual(report["status"], "syntax-failed")
        self.assertEqual(report["checks"][0]["status"], "passed")
        self.assertEqual(report["checks"][2]["status"], "not-run")

    def test_timeouts_and_unavailable_checks_are_not_success(self):
        with patch("recursa.verification.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 1)):
            report = check_sources([{"path": "app.js", "content": "valid"}], node_executable="node")
        self.assertEqual(report["checks"][0]["status"], "timeout")
        self.assertEqual(report["status"], "syntax-failed")
        report = check_sources([{"path": "app.ts", "content": "export const v: number = 1;"}])
        self.assertEqual(report["status"], "not-checked")
        self.assertIsNone(report["typecheck_success"])
        self.assertEqual(check_sources([{"path": "data.json", "content": '{"v": NaN}'}])["status"], "syntax-failed")
