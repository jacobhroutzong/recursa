import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from recursa.experiments import ROOT, fingerprint, load_config, run_batch


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_temp = tempfile.tempdir
        (ROOT / ".cache/test-tmp").mkdir(parents=True, exist_ok=True)
        tempfile.tempdir = str(ROOT / ".cache/test-tmp")

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls.previous_temp

    def test_real_cpu_batch_resume_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = run_batch(ROOT / "configs/smoke.json", Path(tmp))
            run = directory / "trial-001/run.json"
            before = run.stat().st_mtime_ns
            self.assertEqual(json.loads(run.read_text())["metrics"]["model_calls"], 0)
            self.assertTrue((directory / "recursa-artifacts.zip").exists())
            with patch("recursa.experiments.subprocess.run", side_effect=AssertionError("rerun")):
                self.assertEqual(run_batch(ROOT / "configs/smoke.json", Path(tmp)), directory)
            self.assertEqual(before, run.stat().st_mtime_ns)

    def test_config_fingerprint_and_live_rejection(self):
        config, spec = load_config(ROOT / "configs/smoke.json")
        changed = dict(config, trials=2)
        self.assertNotEqual(fingerprint(config, spec), fingerprint(changed, spec))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_batch(ROOT / "configs/live.example.json", Path(tmp), True)

    def test_timeout_checkpoint_and_resume_interrupted_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("recursa.experiments.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 0.1)):
                directory = run_batch(ROOT / "configs/smoke.json", Path(tmp))
            checkpoint = directory / "trial-001/checkpoint.json"
            self.assertEqual(json.loads(checkpoint.read_text())["status"], "timeout")
            checkpoint.write_text('{"status":"running"}')
            run_batch(ROOT / "configs/smoke.json", Path(tmp))
            self.assertEqual(json.loads(checkpoint.read_text())["status"], "complete")

    def test_budget_and_traversal_rejected(self):
        config, _ = load_config(ROOT / "configs/smoke.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            for key, value in (("max_wall_seconds", 0), ("max_cost_usd", float("inf")), ("max_calls", -1)):
                config["budget"][key] = value
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    load_config(path)
                config, _ = load_config(ROOT / "configs/smoke.json")
            config["spec"] = "../../private.json"
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(path)
