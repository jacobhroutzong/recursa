import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from recursa.server import make_handler
from recursa.experiments import ROOT, atomic_json
from recursa.engine import run_smoke


class ServerTests(unittest.TestCase):
    def test_http_replay_routes_and_boundary(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            run = run_smoke({"name": "Test", "requirements": [{"id": "R1", "text": "Test"}]})
            atomic_json(Path(tmp) / "run.json", run)
            atomic_json(Path(tmp) / "private/run.json", dict(run, id="private-should-not-be-served"))
            atomic_json(Path(tmp) / "copied-replay.json", dict(run, id="private-copied", visibility="private"))
            atomic_json(Path(tmp) / "artifacts/generated.json", dict(run, id="generated-record-shaped-source"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Path(tmp)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/runs") as response:
                    archive = json.loads(response.read())
                    self.assertEqual([r["id"] for r in archive], [run["id"]])
                with urlopen(base + "/") as response:
                    self.assertIn(b"Recursa", response.read())
                    self.assertIn("frame-src 'none'", response.headers["Content-Security-Policy"])
                with urlopen(base + "/api/progress") as response:
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertIn("phase", json.loads(response.read()))
                with urlopen(base + "/api/playground") as response:
                    catalog = json.load(response)
                self.assertEqual([item["key"] for item in catalog["presets"]], ["tasks", "operations", "aviation"])
                for preset in catalog["presets"]:
                    self.assertEqual(preset["replay"]["mode"], "deterministic-smoke")
                    self.assertIsNone(preset["replay"]["metrics"]["functional_success"])
                reference = catalog["reference"]
                self.assertEqual(reference["mode"], "human-authored-reference")
                self.assertTrue(reference["metrics"]["functional_success"])
                with urlopen(base + "/assets/task-preview.png") as response:
                    self.assertEqual(response.headers["Content-Type"], "image/png")
                    preview = response.read()
                self.assertTrue(preview.startswith(b"\x89PNG"))
                self.assertEqual(hashlib.sha256(preview).hexdigest(),
                                 reference["events"][-1]["details"]["screenshot_sha256"])
                generated = catalog["generated"]
                self.assertEqual(generated["mode"], "rlm-local-synthesis")
                self.assertTrue(generated["metrics"]["functional_success"])
                self.assertIsNone(generated["metrics"]["requirement_satisfaction"])
                with urlopen(base + "/assets/generated-task-preview.png") as response:
                    self.assertEqual(response.headers["Content-Type"], "image/png")
                    generated_preview = response.read()
                self.assertEqual(hashlib.sha256(generated_preview).hexdigest(),
                                 generated["events"][-1]["details"]["screenshot_sha256"])
                replay_url = base + "/assets/task-replay/"
                with urlopen(replay_url + "manifest.json") as response:
                    replay = json.load(response)
                self.assertEqual(replay["run_id"], generated["id"])
                self.assertEqual(replay["artifacts"], {a["path"]: a["sha256"] for a in generated["artifacts"]})
                scenarios = (ROOT / "examples/specs/tasks-local-acceptance.json").read_bytes()
                self.assertEqual(replay["scenarios_sha256"], hashlib.sha256(scenarios).hexdigest())
                self.assertEqual([(c["id"], c["checked_steps"]) for c in replay["chapters"]],
                                 [(s["id"], len(s["steps"])) for s in json.loads(scenarios)])
                for chapter in replay["chapters"]:
                    for frame in chapter["frames"]:
                        with urlopen(replay_url + frame["file"]) as response:
                            self.assertEqual(response.headers["Content-Type"], "image/png")
                            self.assertEqual(hashlib.sha256(response.read()).hexdigest(), frame["sha256"])
                with urlopen(base + "/api/task-comparison") as response:
                    self.assertEqual(response.headers["Content-Type"], "application/json")
                    comparison = json.load(response)
                self.assertEqual(comparison["spec_sha256"], hashlib.sha256(
                    json.dumps(generated["spec"], sort_keys=True).encode()).hexdigest())
                self.assertEqual(comparison["original_scenarios_sha256"], hashlib.sha256(scenarios).hexdigest())
                adapted = [{**scenario, "source_path": "index.html"} for scenario in json.loads(scenarios)]
                self.assertEqual(comparison["scenarios_sha256"], hashlib.sha256(
                    json.dumps(adapted, sort_keys=True).encode()).hexdigest())
                self.assertEqual(comparison["paid_api_calls"], 0)
                self.assertEqual(comparison["budget"]["max_repairs"], 0)
                self.assertEqual([trial["method"] for trial in comparison["trials"]],
                                 ["direct", "structured", "rlm"])
                for trial in comparison["trials"]:
                    checks = trial["scenarios"]
                    self.assertIsNone(trial["requirement_satisfaction"])
                    self.assertGreater(trial["usage"]["completed_calls"], 0)
                    if checks:
                        self.assertEqual([check["id"] for check in checks], [s["id"] for s in adapted])
                        self.assertEqual(trial["end_to_end_pass_rate"],
                                         sum(check["status"] == "passed" for check in checks) / len(checks))
                    else:
                        self.assertIsNone(trial["end_to_end_pass_rate"])
                with urlopen(base + "/api/comparison-series") as response:
                    self.assertEqual(response.headers["Content-Type"], "application/json")
                    series = json.load(response)
                self.assertEqual([case["id"] for case in series["cases"]], ["tasks", "operations"])
                self.assertEqual(series["total_trials"], 12)
                for case in series["cases"]:
                    source = ROOT / "examples/specs"
                    scenario_file = source / (case["id"] + "-local-acceptance.json")
                    spec = generated["spec"] if case["id"] == "tasks" else json.loads(
                        (source / "operations-local-reviewed.json").read_bytes())
                    ids = [s["id"] for s in json.loads(scenario_file.read_bytes())]
                    self.assertEqual(case["requirement_count"], len(spec["requirements"]))
                    self.assertEqual(case["scenario_count"], len(ids))
                    self.assertEqual([block["settings"]["seed"] for block in case["blocks"]], [17, 73])
                    for block in case["blocks"]:
                        self.assertEqual(block["spec_sha256"], hashlib.sha256(
                            json.dumps(spec, sort_keys=True).encode()).hexdigest())
                        self.assertEqual(block["original_scenarios_sha256"],
                                         hashlib.sha256(scenario_file.read_bytes()).hexdigest())
                        self.assertEqual(block["budget"], comparison["budget"])
                        self.assertEqual(block["weights_sha256"], comparison["weights_sha256"])
                        self.assertEqual(block["paid_api_calls"], 0)
                        self.assertCountEqual([trial["method"] for trial in block["trials"]],
                                              ["direct", "structured", "rlm"])
                        for trial in block["trials"]:
                            self.assertGreater(trial["usage"]["reserved_calls"], 0)
                            self.assertIsNone(trial["requirement_satisfaction"])
                            if trial["end_to_end_pass_rate"] is not None:
                                self.assertEqual([check["id"] for check in trial["scenarios"]], ids)
                with urlopen(base + "/api/repair-series") as response:
                    paired = json.load(response)
                self.assertEqual(paired["kind"], "matched-local-repair-series")
                self.assertEqual(paired["total_trials"], 12)
                self.assertEqual(paired["repair_budget"]["max_calls"], 1)
                self.assertEqual(paired["repair_budget"]["max_cost_usd"], 0)
                for old_case, case in zip(series["cases"], paired["cases"], strict=True):
                    self.assertEqual(case["id"], old_case["id"])
                    for old, block in zip(old_case["blocks"], case["blocks"], strict=True):
                        for field in ("spec_sha256", "scenarios_sha256", "budget", "settings", "weights_sha256"):
                            self.assertEqual(block[field], old[field])
                        self.assertEqual(block["repair_budget"], paired["repair_budget"])
                        self.assertCountEqual([trial["method"] for trial in block["trials"]],
                                              ["direct", "structured", "rlm"])
                        for trial in block["trials"]:
                            repair = trial["repair"]
                            self.assertIn(repair["attempts"], (0, 1))
                            if repair["usage"] is not None:
                                self.assertLessEqual(repair["usage"]["reserved_calls"], 1)
                            if repair["after"] is not None:
                                self.assertEqual(repair["attempts"], 1)
                                self.assertGreater(repair["changed_files"], 0)
                                self.assertIsNotNone(repair["recheck_wall_ms"])
                                self.assertIsNone(repair["after"]["requirement_satisfaction"])
                            if repair["status"] == "no-verified-candidate":
                                self.assertEqual(repair["attempts"], 0)
                                self.assertIsNone(repair["after"])
                for route in ("/../README.md", "/api/execute", "/assets/unknown.png", "/assets/task-replay/../generated-task-preview.png", "/api/runs/missing", "/api/runs/private-copied", "/api/runs/generated-record-shaped-source"):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base + route)
                    self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
