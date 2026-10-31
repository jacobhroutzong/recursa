from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch

from recursa.build import build_application
from recursa.pipeline import verify_application
from recursa.typecheck import check_types

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    folder = ROOT / 'examples/fixtures/react-counter'
    artifacts = [{'path': p.relative_to(folder).as_posix(), 'content': p.read_text(encoding='utf-8'), 'requirements': ['REACT-01']}
                 for p in sorted(folder.rglob('*')) if p.suffix in {'.html', '.tsx'}]
    return artifacts


class ReactApplicationTests(unittest.TestCase):
    def test_missing_runtime_is_unmeasured_instead_of_an_application_failure(self):
        import json
        reply = subprocess.CompletedProcess('node', 1, json.dumps({'status': 'unavailable', 'version': '0.28.2',
            'errors': [{'path': 'src/main.tsx', 'text': 'Pinned React toolchain unavailable'}]}), '')
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.build.subprocess.run', return_value=reply):
            report = build_application(fixture(), tmp)
            self.assertEqual(report['status'], 'unavailable')
            self.assertIsNone(report['build_success'])
            self.assertFalse(any(c['status'] == 'failed' for c in report['checks']))

    def test_real_typed_build_and_hook_state_in_browser(self):
        spec = {'requirements': [{'id': 'REACT-01', 'text': 'Increment twice and reset the labeled counter'}]}
        scenarios = [{'id': 'counter', 'requirements': ['REACT-01'], 'source_path': 'src/Counter.tsx', 'steps': [
            {'action': 'expect_text', 'target': {'role': 'status', 'name': 'Count'}, 'value': 'Count: 0'},
            {'action': 'click', 'target': {'role': 'button', 'name': 'Increment'}},
            {'action': 'click', 'target': {'role': 'button', 'name': 'Increment'}},
            {'action': 'expect_text', 'target': {'role': 'status', 'name': 'Count'}, 'value': 'Count: 2'},
            {'action': 'click', 'target': {'role': 'button', 'name': 'Reset'}},
            {'action': 'expect_text', 'target': {'role': 'status', 'name': 'Count'}, 'value': 'Count: 0'},
            {'action': 'audit_accessibility'}]}]
        with tempfile.TemporaryDirectory() as tmp:
            report = verify_application(spec, fixture(), tmp, scenarios=scenarios,
                typescript_directory=ROOT / 'tooling/typecheck/node_modules/typescript')
            self.assertEqual(report['status'], 'passed', report['verification'])
            self.assertTrue(report['verification']['typecheck_success'])
            self.assertTrue(report['verification']['functional_success'])
            self.assertTrue(report['verification']['accessibility_success'])
            build = report['verification']['stages']['build']
            notice = Path(build['dist_path']) / 'THIRD_PARTY_LICENSES.txt'
            self.assertTrue(notice.exists())
            self.assertIn('react-dom@19.3.1', notice.read_text())

    def test_wrong_component_prop_fails_actual_typechecker(self):
        artifacts = fixture()
        main = next(a for a in artifacts if a['path'] == 'src/main.tsx')
        main['content'] = main['content'].replace('initial={0}', 'initial="wrong"')
        report = check_types(artifacts, ROOT / 'tooling/typecheck/node_modules/typescript')
        self.assertFalse(report['typecheck_success'], report)
        self.assertTrue(any(c['path'] == 'src/main.tsx' and c['status'] == 'failed' for c in report['checks']))

    def test_private_packages_and_host_imports_stay_blocked(self):
        for request in ('react/cjs/react.production.js', 'scheduler', 'fs', 'https://invalid.example/a.js'):
            artifacts = fixture()
            main = next(a for a in artifacts if a['path'] == 'src/main.tsx')
            main['content'] = f'import {request!r};'
            with tempfile.TemporaryDirectory() as tmp:
                report = build_application(artifacts, tmp)
                self.assertFalse(report['build_success'], (request, report))
