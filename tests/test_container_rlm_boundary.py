"""Parent-side rejection tests, not evidence of RLM reasoning or isolation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recursa.container_rlm import run_fixture, runtime_source_hash

IMAGE = 'sha256:' + 'a' * 64


class ContainerRLMParentTests(unittest.TestCase):
    def record(self):
        return {'image_id': IMAGE, 'runtime_source_sha256': runtime_source_hash(), 'platform': 'linux/amd64'}

    def test_stale_image_rejected_before_execution(self):
        record = self.record()
        record['runtime_source_sha256'] = 'stale'
        with patch('recursa.container_rlm.run_python') as execute:
            with self.assertRaises(ValueError):
                run_fixture(IMAGE, 'unused', runtime_record=record)
            execute.assert_not_called()

    def test_container_failure_has_no_artifact_or_success_claim(self):
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.container_rlm.run_python', return_value={'status': 'unavailable'}):
            result = run_fixture(IMAGE, Path(tmp) / 'run', runtime_record=self.record())
            self.assertEqual(result['status'], 'container-failed')
            self.assertFalse(result['live_inference'])
            self.assertFalse((Path(tmp) / 'run/artifacts').exists())

    def test_returned_path_escape_and_false_provenance_are_rejected(self):
        for mode, path in [('offline-scripted-container', '../escape.ts'), ('rlm-live', 'valid.ts')]:
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp) / 'run'
                def execute(*args, **kwargs):
                    (directory / 'private').mkdir(parents=True)
                    data = {'kind': 'offline-scripted-container', 'live_inference': False, 'run': {
                        'mode': mode, 'live_inference': False, 'artifacts': [{'path': path, 'requirements': ['R1'], 'content': 'export const n=1;'}]}}
                    (directory / 'private/stdout.bin').write_text(json.dumps(data))
                    return {'status': 'completed', 'policy_verified': True, 'cleanup_verified': True}
                with patch('recursa.container_rlm.run_python', side_effect=execute):
                    with self.assertRaises(ValueError):
                        run_fixture(IMAGE, directory, runtime_record=self.record())
                self.assertFalse((Path(tmp) / 'escape.ts').exists())
                self.assertFalse((directory / 'artifacts').exists())

    def test_invalid_fixture_budget_rejected(self):
        with patch('recursa.container_rlm.run_python') as execute:
            for value in (0, 4, True):
                with self.assertRaises(ValueError):
                    run_fixture(IMAGE, 'unused', max_calls=value)
            execute.assert_not_called()
