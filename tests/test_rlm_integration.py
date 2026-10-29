"""Scripted HTTP transport integration. These are NOT genuine model runs."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recursa.experiments import ROOT


@unittest.skipUnless(importlib.util.find_spec("rlm"), "Install requirements-live.lock for official runtime integration tests")
class OfficialRuntimeIntegrationTests(unittest.TestCase):
    def config(self):
        return {"trusted_local_execution": True, "models": {"root": "scripted-root", "sub": "scripted-sub"},
                "provider": {"base_url": "http://127.0.0.1:9999/v1", "api_key_env": "RECURSA_TEST_KEY"},
                "rates": {name: {"input_per_million": 0, "output_per_million": 0} for name in ("scripted-root", "scripted-sub")},
                "max_iterations": 3, "per_call_output_tokens": 2048,
                "budget": {"max_calls": 4, "max_output_tokens": 8192, "max_input_bytes": 100000,
                           "max_wall_seconds": 30, "max_cost_usd": 0, "max_depth": 1,
                           "max_concurrency": 1, "max_repairs": 0}}

    def test_official_external_context_repl_and_subcall_wiring(self):
        import httpx
        import openai
        from recursa.live import run_live
        original = openai.OpenAI
        requests = []
        sentinel = "SPEC_BODY_MUST_STAY_EXTERNAL_84712"
        artifact = {"artifacts": [{"path": "src/task.ts", "content": "export const titleValid = (v: string) => v.trim().length > 0;", "requirements": ["R1"]}]}

        def transport(request):
            body = json.loads(request.content)
            requests.append(body)
            if body["model"] == "scripted-root":
                self.assertNotIn(sentinel, json.dumps(body["messages"]))
                content = '```repl\nimport json\nrows = read_requirements(["R1"])\nset_task_plan([{"id":"task","label":"Task contract","kind":"contract","requirements":["R1"]}])\nbegin_task("task")\ndrafted = llm_query("Produce artifact JSON for " + json.dumps(rows))\nsubmitted = submit_task_output("task", json.loads(drafted))\nanswer["content"] = json.dumps({"artifact_paths": submitted["artifact_paths"]})\nanswer["ready"] = True\n```'
            else:
                self.assertIn(sentinel, json.dumps(body["messages"]))
                content = json.dumps(artifact)
            return httpx.Response(200, json={"id": "scripted", "object": "chat.completion", "created": 0,
                "model": body["model"], "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50}})

        def client_factory(**kwargs):
            return original(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))

        (ROOT / ".cache").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp, patch.dict(os.environ, {"RECURSA_TEST_KEY": "offline-placeholder"}), patch("openai.OpenAI", side_effect=client_factory):
            run = run_live({"name": "Scripted integration ONLY", "requirements": [{"id": "R1", "text": sentinel}]}, Path(tmp), self.config(), authorize_live=True)
            self.assertEqual(run["status"], "completed", run["events"])
            self.assertEqual(run["metrics"]["model_calls"], 2)
            self.assertTrue(any(e["type"] == "subcall" for e in run["events"]))
            self.assertTrue((Path(tmp) / "artifacts/src/task.ts").exists())
            self.assertEqual(len(requests), 2)
            # Raw upstream state is private; sanitized public events do not contain credentials.
            self.assertNotIn("offline-placeholder", json.dumps(run))
            self.assertTrue((Path(tmp) / "private/trajectory.json").exists())
            self.assertEqual(run["verification"]["status"], "not-checked", "Fixture TypeScript has no configured compiler")
            self.assertIsNone(run["verification"]["functional_success"])
            self.assertEqual(run["coverage"]["referenced_requirements"], 1)
            limited = self.config()
            limited["budget"]["max_calls"] = 1
            stopped = run_live({"requirements": [{"id": "R1", "text": sentinel}]}, Path(tmp) / "limited", limited, authorize_live=True)
            self.assertEqual(stopped["status"], "budget-exhausted")
            self.assertEqual(stopped["metrics"]["model_calls"], 1)
            self.assertEqual(len(requests), 3, "Exhausted subcall must never reach HTTP transport")
            self.assertTrue((Path(tmp) / "limited/partial-run.json").exists())

    def test_unauthorized_and_untrusted_runs_fail_before_provider(self):
        from recursa.live import run_live, validate_live_config
        with self.assertRaises(ValueError):
            run_live({}, Path("unused"), self.config())
        config = self.config()
        config["trusted_local_execution"] = False
        with self.assertRaises(ValueError):
            validate_live_config(config)
