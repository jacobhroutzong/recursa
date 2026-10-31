import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from recursa.processes import BoundaryUnavailable, run_worker
from recursa.worker import ROOT, run_offline_application


class ProcessBoundaryTests(unittest.TestCase):
    def launch(self, tmp, mode, timeout):
        return run_worker([sys.executable, str(ROOT / 'tests/fixtures/lifetime_worker.py')],
            json.dumps({'directory': tmp, 'mode': mode}).encode(), timeout=timeout, cwd=ROOT)

    def assert_child_stopped(self, tmp):
        self.assertTrue(Path(tmp, 'started.txt').exists())
        pid = int(Path(tmp, 'child-pid.txt').read_text())
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
                    self.assertNotEqual(code.value, 259, 'Descendant must not remain active')
                finally:
                    api.CloseHandle(handle)
        heartbeat = Path(tmp, 'heartbeat.txt')
        time.sleep(0.1)
        before = heartbeat.read_bytes() if heartbeat.exists() else None
        time.sleep(0.2)
        self.assertEqual(heartbeat.read_bytes() if heartbeat.exists() else None, before)

    def test_normal_exit_cleans_descendants(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp:
            report = self.launch(tmp, 'spawn-exit', 10)
            self.assertEqual(report['status'], 'complete', report)
            self.assertFalse(report['sandbox'])
            self.assert_child_stopped(tmp)

    @unittest.skipUnless(importlib.util.find_spec('rlm'), 'Install official runtime for blocked REPL regression')
    def test_hard_deadline_kills_actual_blocked_repl_and_descendant(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp:
            report = self.launch(tmp, 'hang-rlm', 10)
            self.assertEqual(report['status'], 'timeout', report)
            self.assertLess(report['duration_seconds'], 15)
            self.assert_child_stopped(tmp)

    def test_offline_application_passes_in_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp:
            output = Path(tmp) / 'application-worker'
            report = run_offline_application(output, max_wall_seconds=45)
            self.assertEqual(report['status'], 'complete', report)
            measured = json.loads((output / 'application/application-report.json').read_text())
            self.assertTrue(measured['verification']['functional_success'])
            self.assertTrue((output / 'worker-report.json').exists())

    def test_boundary_creation_failure_does_not_spawn(self):
        if os.name != 'nt':
            self.skipTest('Windows job failure case')
        with patch('recursa.processes._WindowsJob', side_effect=BoundaryUnavailable('unavailable')), patch('recursa.processes.subprocess.Popen') as spawn:
            with self.assertRaises(BoundaryUnavailable):
                run_worker([sys.executable, '-m', 'recursa.worker'], b'{}', timeout=1)
            spawn.assert_not_called()

    def test_invalid_timeout_rejected_without_execution(self):
        for value in (0, -1, float('nan'), True):
            with self.assertRaises(ValueError):
                run_worker([sys.executable], b'{}', timeout=value)

    def test_cancellation_cleans_worker_and_descendant(self):
        communicate = subprocess.Popen.communicate
        def interrupt(process, payload, timeout):
            try:
                communicate(process, payload, timeout=1)
            except subprocess.TimeoutExpired:
                raise KeyboardInterrupt
            self.fail('Fixture should be blocked until cancellation')
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp, patch('recursa.processes.subprocess.Popen.communicate', new=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.launch(tmp, 'spawn-hang', 10)
            self.assert_child_stopped(tmp)

    def test_assignment_failure_does_not_release_workload(self):
        if os.name != 'nt':
            self.skipTest('Windows job assignment case')
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp, patch('recursa.processes._WindowsJob.assign', side_effect=BoundaryUnavailable('assignment failed')):
            with self.assertRaises(BoundaryUnavailable):
                self.launch(tmp, 'spawn-exit', 10)
            self.assertFalse(Path(tmp, 'started.txt').exists())

    def test_offline_cancellation_is_persisted_without_claiming_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as tmp, patch('recursa.worker.run_worker', side_effect=KeyboardInterrupt):
            output = Path(tmp) / 'cancelled'
            with self.assertRaises(KeyboardInterrupt):
                run_offline_application(output, max_wall_seconds=10)
            report = json.loads((output / 'worker-report.json').read_text())
            self.assertEqual(report['status'], 'cancelled')
            self.assertFalse(report['live_inference'])
