import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from recursa.baseline import run_direct
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
