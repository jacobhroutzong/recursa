import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from recursa.processes import BoundaryUnavailable, run_worker
from recursa.provider import ProviderFailure
from recursa.provider_worker import ROOT, SupervisedProviderAdapter
from test_provider import config, MESSAGES


@unittest.skipUnless(importlib.util.find_spec('httpx'), 'Optional HTTP dependency not installed')
class ProviderWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / '.cache')
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.env = patch.dict('os.environ', {'RECURSA_TEST_KEY': 'fake-test-credential'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.launches = 0

        def offline(command, payload, **options):
            self.launches += 1
            self.assertNotIn(b'fake-test-credential', payload)
            return run_worker([sys.executable, str(ROOT / 'tests/fixtures/provider_worker.py')], payload, **options)

        self.launch = patch('recursa.provider_worker.run_worker', side_effect=offline)
        self.launch.start()
        self.addCleanup(self.launch.stop)

    def adapter(self, *, seconds=30, calls=2):
        cfg = config()
        cfg['budget'].update(max_wall_seconds=seconds, max_calls=calls)
        return SupervisedProviderAdapter(cfg, self.directory / 'private', authorize_live=True)

    def test_real_worker_success_and_parent_budget_survives_worker_exit(self):
        adapter = self.adapter(calls=1)
        self.assertEqual(adapter.complete('fixture', MESSAGES), 'fixture reply')
        with self.assertRaisesRegex(ProviderFailure, 'BudgetExceeded'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(self.launches, 1)
        summary = adapter.summary()
        self.assertEqual(summary['reserved_calls'], 1)
        self.assertEqual(summary['events'][0]['provider_reported_usage']['total_tokens'], 8)
        directory = self.directory / 'private/call-000001'
        report = json.loads((directory / 'worker-report.json').read_text())
        self.assertEqual(report['status'], 'complete')
        self.assertNotIn('live_inference', report)
        self.assertFalse(report['sandbox'])
        for path in directory.glob('*.json'):
            self.assertNotIn('fake-test-credential', path.read_text())
            self.assertNotIn('private fixture prompt', path.read_text())

    def test_real_http_failure_is_sanitized_and_stops_session(self):
        adapter = self.adapter()
        with self.assertRaisesRegex(ProviderFailure, '^ProviderHTTPError$'):
            adapter.complete('fixture', [{'role': 'user', 'content': 'http-error'}])
        with self.assertRaisesRegex(ProviderFailure, '^AdapterClosed$'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(self.launches, 1)
        self.assertEqual(adapter.summary()['reserved_calls'], 1)
        for path in (self.directory / 'private').rglob('*.json'):
            self.assertNotIn('private-provider-body', path.read_text())

    def assert_descendant_stopped(self):
        self.assertTrue((self.directory / 'started.txt').exists())
        pid = int((self.directory / 'child-pid.txt').read_text())
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes as w
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
            api.OpenProcess.restype = w.HANDLE
            api.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
            api.CloseHandle.argtypes = [w.HANDLE]
            handle = api.OpenProcess(0x1000, False, pid)
            if handle:
                try:
                    code = w.DWORD()
                    self.assertTrue(api.GetExitCodeProcess(handle, ctypes.byref(code)))
                    self.assertNotEqual(code.value, 259)
                finally:
                    api.CloseHandle(handle)
        else:
            # The process may briefly remain a zombie after its group is killed.
            state = Path(f'/proc/{pid}/stat')
            if state.exists():
                self.assertEqual(state.read_text().split()[2], 'Z')

    def test_real_blocked_transport_times_out_and_kills_descendant(self):
        adapter = self.adapter(seconds=3)
        with self.assertRaisesRegex(ProviderFailure, '^ProviderWorkerTimeout$'):
            adapter.complete('fixture', [{'role': 'user', 'content': 'hang:' + str(self.directory)}])
        self.assert_descendant_stopped()
        self.assertEqual(adapter.summary()['reserved_calls'], 1)
        report = json.loads((self.directory / 'private/call-000001/worker-report.json').read_text())
        self.assertEqual(report['status'], 'timeout')
        self.assertTrue(report['reservation_retained'])
        self.assertLess(report['duration_seconds'], 8)

    def test_cancellation_is_durable_and_closes_adapter(self):
        adapter = self.adapter()
        communicate = subprocess.Popen.communicate

        def interrupt(process, payload, timeout):
            try:
                communicate(process, payload, timeout=2)
            except subprocess.TimeoutExpired:
                raise KeyboardInterrupt
            self.fail('Scripted transport should still be blocked')

        with patch('recursa.processes.subprocess.Popen.communicate', new=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                adapter.complete('fixture', [{'role': 'user', 'content': 'hang:' + str(self.directory)}])
        self.assert_descendant_stopped()
        self.assertEqual(adapter.summary()['stop_reason'], 'ProviderCancelled')
        with self.assertRaisesRegex(ProviderFailure, 'AdapterClosed'):
            adapter.complete('fixture', MESSAGES)
        report = json.loads((self.directory / 'private/call-000001/worker-report.json').read_text())
        self.assertEqual(report['status'], 'cancelled')
        durable = json.loads((self.directory / 'private/session-report.json').read_text())
        self.assertEqual(durable['stop_reason'], 'ProviderCancelled')
        self.assertEqual(durable['reserved_calls'], 1)

    def test_authorization_missing_key_and_boundary_failure_do_not_dispatch(self):
        with self.assertRaises(ValueError):
            SupervisedProviderAdapter(config(), self.directory / 'unauthorized')
        self.assertFalse((self.directory / 'unauthorized').exists())
        adapter = self.adapter()
        with patch.dict('os.environ', {'RECURSA_TEST_KEY': ''}), self.assertRaisesRegex(ProviderFailure, 'CredentialUnavailable'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(self.launches, 0)
        self.assertEqual(adapter.summary()['reserved_calls'], 0)
        other = SupervisedProviderAdapter(config(), self.directory / 'boundary', authorize_live=True)
        with patch('recursa.provider_worker.run_worker', side_effect=BoundaryUnavailable('private OS error')):
            with self.assertRaisesRegex(ProviderFailure, '^ProviderWorkerUnavailable$'):
                other.complete('fixture', MESSAGES)
        self.assertEqual(other.summary()['reserved_calls'], 1)
        report = json.loads((self.directory / 'boundary/call-000001/worker-report.json').read_text())
        self.assertEqual(report['error_classification'], 'ProviderWorkerUnavailable')
        self.assertNotIn('private OS error', json.dumps(report))

    def test_missing_oversized_and_malformed_worker_results_do_not_succeed(self):
        cases = (None, b'x' * 500001, b'not-json', b'{"ok": true, "text": "x"}',
                 b'{"ok": false, "error_classification": "private injected error"}',
                 b'{"ok": true, "text": "x", "usage": {"prompt_tokens": 1}}')
        for index, contents in enumerate(cases):
            adapter = SupervisedProviderAdapter(config(), self.directory / f'corrupt-{index}', authorize_live=True)

            def corrupt(command, payload, **options):
                output = Path(json.loads(payload)['output'])
                if contents is not None:
                    (output / 'response.json').write_bytes(contents)
                return {'status': 'complete', 'live_inference': False}

            with patch('recursa.provider_worker.run_worker', side_effect=corrupt), self.assertRaises(ProviderFailure):
                adapter.complete('fixture', MESSAGES)
            self.assertEqual(adapter.summary()['reserved_calls'], 1)
            self.assertNotIn('private injected error', json.dumps(adapter.summary()))
            with self.assertRaisesRegex(ProviderFailure, 'AdapterClosed'):
                adapter.complete('fixture', MESSAGES)

    def test_parent_revalidates_usage_and_fails_closed_on_record_error(self):
        adapter = self.adapter()

        def overrun(command, payload, **options):
            output = Path(json.loads(payload)['output'])
            (output / 'response.json').write_text(json.dumps({'ok': True, 'text': 'fixture reply',
                'usage': {'prompt_tokens': 5, 'completion_tokens': 33, 'total_tokens': 38}}))
            return {'status': 'complete'}

        with patch('recursa.provider_worker.run_worker', side_effect=overrun), self.assertRaisesRegex(ProviderFailure, 'UsageExceededReservation'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(adapter.summary()['reserved_calls'], 1)
        other = SupervisedProviderAdapter(config(), self.directory / 'record-failure', authorize_live=True)
        with patch('recursa.provider_worker.atomic_json', side_effect=OSError('private path')), self.assertRaisesRegex(ProviderFailure, 'ProviderRecordUnavailable'):
            other.complete('fixture', MESSAGES)
        self.assertEqual(other.summary()['stop_reason'], 'ProviderRecordUnavailable')
        self.assertEqual(other.summary()['reserved_calls'], 1)
