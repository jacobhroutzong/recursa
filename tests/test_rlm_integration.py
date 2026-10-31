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
        config = self.config()
        config['budget']['max_repairs'] = 1
        with self.assertRaises(ValueError):
            validate_live_config(config)
        config['application_verification'] = {'scenarios': [], 'arbitrary_code': 'forbidden'}
        with self.assertRaises(ValueError):
            validate_live_config(config)

    def test_application_verification_and_repair_share_offline_transport_budget(self):
        import httpx
        import openai
        from copy import deepcopy
        from recursa.live import run_live
        from recursa.offline import fixture
        original_client = openai.OpenAI
        spec, artifacts, scenarios = fixture()
        broken = deepcopy(artifacts)
        main = next(a for a in artifacts if a['path'] == 'src/main.ts')
        next(a for a in broken if a['path'] == 'src/main.ts')['content'] = main['content'].replace('completed: false', 'completed: true')
        refs = [r['id'] for r in spec['requirements']]
        requests = []

        def transport(request):
            body = json.loads(request.content)
            requests.append(body)
            if body['model'] == 'scripted-root':
                code = '\n'.join([
                    'import json', 'rows = read_requirements(' + json.dumps(refs) + ')',
                    'set_task_plan(' + json.dumps([{'id': 'app', 'label': 'Offline fixture only', 'kind': 'assembly', 'requirements': refs}]) + ')',
                    'begin_task("app")', 'drafted = llm_query("Return the scripted fixture artifacts")',
                    'submitted = submit_task_output("app", json.loads(drafted))',
                    'answer["content"] = json.dumps({"artifact_paths": submitted["artifact_paths"]})',
                    'answer["ready"] = True'])
                content = '```repl\n' + code + '\n```'
            elif 'allowed_paths' in body['messages'][-1]['content']:
                context = json.loads(body['messages'][-1]['content'])
                self.assertEqual(context['allowed_paths'], ['src/main.ts'])
                self.assertTrue(context['declared_dependency_contracts'])
                content = json.dumps({'artifacts': [main]})
            else:
                content = json.dumps({'artifacts': broken})
            return httpx.Response(200, json={'id': 'offline-only', 'object': 'chat.completion', 'created': 0,
                'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'total_tokens': 50}})

        def client_factory(**kwargs):
            return original_client(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))

        config = self.config()
        config['budget'].update(max_calls=3, max_output_tokens=30000, max_input_bytes=500000, max_wall_seconds=90, max_repairs=1)
        config['per_call_output_tokens'] = 10000
        config['application_verification'] = {'scenarios': scenarios}
        config['typescript_compiler_directory'] = str(ROOT / 'tooling/typecheck/node_modules/typescript')
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp, patch.dict(os.environ, {'RECURSA_TEST_KEY': 'offline-placeholder'}), patch('openai.OpenAI', side_effect=client_factory):
            run = run_live(spec, Path(tmp) / 'verified', config, authorize_live=True)
            self.assertEqual(run['status'], 'completed', run['events'])
            self.assertEqual(run['repair_attempts'], 1)
            self.assertEqual(run['repair_status'], 'rechecked')
            self.assertTrue(run['metrics']['functional_success'])
            self.assertTrue(run['metrics']['build_success'])
            self.assertEqual(run['metrics']['model_calls'], 3)
            self.assertEqual(len(requests), 3)
            self.assertEqual((Path(tmp) / 'verified/artifacts/src/main.ts').read_text(encoding='utf-8'), main['content'])
            self.assertTrue(any(e['label'] == 'repair model request' for e in run['events']))
            self.assertEqual(sum(e['type'] == 'subcall' for e in run['events']), 1)
            self.assertEqual(sum(e['type'] == 'repair-model' for e in run['events']), 1)
            limited = deepcopy(config)
            limited['budget']['max_calls'] = 2
            run = run_live(spec, Path(tmp) / 'limited', limited, authorize_live=True)
            self.assertEqual(run['status'], 'budget-exhausted', run['events'])
            self.assertEqual(run['metrics']['repair_attempts'], 1)
            self.assertEqual(len(requests), 5, 'Denied repair must not dispatch HTTP')
            self.assertTrue((Path(tmp) / 'limited/application/verification-000/verification.json').exists())
            self.assertTrue((Path(tmp) / 'limited/private/trajectory.json').exists())
