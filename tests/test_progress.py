import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recursa.experiments import ROOT
from recursa.progress import build_progress


class ReleaseProgressTests(unittest.TestCase):
    def test_release_requires_exact_ordered_ledger_and_current_evidence(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / ".cache").mkdir()
            ledger = root / "docs/implementation-progress.md"
            ledger.write_text("\n".join(f"| {n}. Section | In progress | Pending verification |" for n in range(1, 22)), encoding="utf-8")
            evidence = root / ".cache/test-evidence.json"
            evidence.write_text(json.dumps({"source_digest": "expected", "failed": 0, "passed": 1}), encoding="utf-8")
            with patch("recursa.progress.ROOT", root), patch("recursa.progress.source_digest", return_value="expected"):
                status = build_progress()
                self.assertEqual(len(status["sections"]), 21)
                self.assertFalse(status["live_inference"])
                evidence.write_text('{"source_digest":"stale"}', encoding="utf-8")
                with self.assertRaises(ValueError):
                    build_progress()
                ledger.write_text("| 1. Incomplete | Pending | Missing other rows |", encoding="utf-8")
                with self.assertRaises(ValueError):
                    build_progress()
