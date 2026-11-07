import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from recursa.baseline import run_direct, run_structured
from recursa.experiments import ROOT
from test_provider import config, result


class DirectBaselineTests(unittest.TestCase):
    def test_direct_full_spec_response_uses_shared_verification(self):
        run = json.loads((ROOT / "apps/studio/generated-task.json").read_bytes())
        scenarios = json.loads((ROOT / "examples/specs/tasks-local-acceptance.json").read_bytes())
        requests = []

        def intercepted_request(adapter, model, messages, key, *, deadline):
            requests.append(messages)
            content = "```json\n" + json.dumps({"artifacts": run["artifacts"]}) + "\n```"
            return result(choices=[{"finish_reason": "stop",
                                    "message": {"role": "assistant", "content": content}}])

        with TemporaryDirectory(dir=ROOT / ".cache") as directory, \
                patch.dict("os.environ", {"RECURSA_TEST_KEY": "offline-fixture"}), \
                patch("recursa.baseline.SupervisedProviderAdapter._request", new=intercepted_request):
            with self.assertRaisesRegex(ValueError, "explicit live authorization"):
                run_direct(run["spec"], scenarios, directory, "fixture", config())
            self.assertEqual(requests, [])
            report = run_direct(run["spec"], scenarios, directory, "fixture", config(), authorize_live=True)
            self.assertEqual(len(requests), 1)
            self.assertEqual(json.loads(requests[0][1]["content"]), run["spec"])
            self.assertNotIn("expect_checked", requests[0][1]["content"])
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["metrics"]["end_to_end_pass_rate"], 1)
            self.assertEqual(report["metrics"]["model_calls"], 1)
            self.assertIsNone(report["metrics"]["requirement_satisfaction"])
            self.assertIsNone(report["metrics"]["cost_usd"])
            self.assertEqual(report["visibility"], "private")
            self.assertEqual(json.loads((Path(directory) / "private/direct-report.json").read_bytes()), report)

    def test_structured_assembly_receives_state_source_and_contract(self):
        spec = {"requirements": [{"id": "B", "text": "Show the saved value.", "depends_on": ["A"]},
                                 {"id": "A", "text": "Provide a value."}]}
        scenarios = [{"id": "render", "requirements": ["B"], "steps": [
            {"action": "expect_text", "target": {"role": "main"}, "value": "Saved"}
        ]}]
        state = {"path": "state.js", "content": "export const value = 'Saved';", "requirements": ["A"],
                 "exports": ["value: string"]}
        assembly = [
            {"path": "index.html", "content": '<!doctype html><html lang="en"><head><title>Test</title></head>'
             '<body><main></main><script type="module" src="app.js"></script></body></html>',
             "requirements": ["B"]},
            {"path": "app.js", "content": "import { value } from './state.js';\n"
             "document.querySelector('main').textContent = value;", "requirements": ["B"]},
        ]
        requests = []

        def intercepted_request(adapter, model, messages, key, *, deadline):
            requests.append(json.loads(messages[-1]["content"]))
            artifacts = [state] if len(requests) == 1 else assembly
            return result(choices=[{"finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"artifacts": artifacts})}}])

        with TemporaryDirectory(dir=ROOT / ".cache") as directory, \
                patch.dict("os.environ", {"RECURSA_TEST_KEY": "offline-fixture"}), \
                patch("recursa.baseline.SupervisedProviderAdapter._request", new=intercepted_request):
            report = run_structured(spec, scenarios, directory, "fixture", config(), authorize_live=True)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["metrics"]["model_calls"], 2)
        self.assertEqual([item["id"] for item in requests[0]["requirements"]], ["A", "B"])
        self.assertEqual(requests[1]["state_source"], state["content"])
        self.assertEqual(requests[1]["state_contract"][0]["exports"], state["exports"])
