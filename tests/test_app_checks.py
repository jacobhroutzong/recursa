import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recursa.app_checks import lint_sources, check_units, validate_unit_cases
from recursa.browser_checks import check_application
from recursa.build import build_application
from recursa.offline import ROOT, fixture
from recursa.pipeline import verify_application


class ApplicationChecksTests(unittest.TestCase):
    def test_partial_audit_stays_unmeasured(self):
        spec, artifacts, scenarios = fixture()
        partial = {'functional_success': False, 'checks': [
            {'path': 'src/main.ts', 'kind': 'browser', 'status': 'failed',
             'accessibility_audits': [{'passed': True, 'findings': []}]}]}
        with tempfile.TemporaryDirectory() as tmp, patch('recursa.pipeline.check_application', return_value=partial):
            result = verify_application(spec, artifacts, tmp, scenarios=scenarios)
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['verification']['accessibility_success'])

    def test_lint_is_measured_without_evaluating_source(self):
        artifacts = [{'path': 'main.ts', 'content': 'var a = 1; debugger; if(a == 1) eval("throw 1");', 'requirements': ['R1']}]
        result = lint_sources(artifacts)
        self.assertFalse(result['lint_success'], result)
        self.assertEqual({d['rule'] for d in result['checks'][0]['diagnostics']},
                         {'no-var', 'no-debugger', 'strict-equality', 'no-direct-eval'})
        artifacts[0]['content'] = 'const a = "var debugger == eval"; // debugger;'
        self.assertTrue(lint_sources(artifacts)['lint_success'])

    def test_missing_linter_is_unmeasured(self):
        _, artifacts, _ = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            report = lint_sources(artifacts, Path(tmp) / 'missing')
            self.assertIsNone(report['lint_success'])

    def test_independent_unit_cases_and_basic_audits_pass(self):
        spec, artifacts, scenarios = fixture()
        cases = json.loads((ROOT / 'examples/fixtures/task-app/unit-cases.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_application(spec, artifacts, tmp, scenarios=scenarios, unit_cases=cases,
                typescript_directory=ROOT / 'tooling/typecheck/node_modules/typescript')
            report = result['verification']
            self.assertEqual(result['status'], 'passed', report)
            self.assertEqual(report['unit_test_pass_rate'], 1)
            self.assertTrue(report['lint_success'])
            self.assertTrue(report['accessibility_success'])
            self.assertEqual(len(report['stages']['unit']['checks']), 6)

    def test_wrong_unit_expectation_is_a_real_failure(self):
        _, artifacts, _ = fixture()
        cases = [{'id': 'wrong', 'module': 'src/model.ts', 'export': 'validTitle',
                  'arguments': [''], 'expected': True, 'requirements': ['TASK-01']}]
        with tempfile.TemporaryDirectory() as tmp:
            result = check_units(artifacts, cases, tmp)
            self.assertEqual(result['status'], 'failed', result)
            self.assertEqual(result['unit_test_pass_rate'], 0)
            self.assertEqual(result['checks'][0]['path'], 'src/model.ts')
            self.assertEqual(result['checks'][0]['kind'], 'unit')

    def test_unit_code_paths_and_nonfinite_values_rejected(self):
        _, artifacts, _ = fixture()
        case = {'id': 'bad', 'module': '../secret.ts', 'export': 'f', 'arguments': [], 'expected': 1, 'requirements': ['TASK-01']}
        with self.assertRaises(ValueError):
            validate_unit_cases([case], artifacts, {'TASK-01'})
        case['module'] = 'src/model.ts'
        case['expected'] = float('nan')
        with self.assertRaises(ValueError):
            validate_unit_cases([case], artifacts, {'TASK-01'})

    def test_basic_audit_detects_missing_name_language_and_landmark(self):
        artifacts = [
            {'path': 'index.html', 'content': '<html><head><title>Bad fixture</title></head><body><h1>Bad fixture</h1><button></button><script type="module" src="main.js"></script></body></html>', 'requirements': ['R1']},
            {'path': 'main.js', 'content': 'export const fixture = true;', 'requirements': ['R1']}]
        with tempfile.TemporaryDirectory() as tmp:
            build = build_application(artifacts, tmp)
            report = check_application(build['dist_path'], [{'id': 'bad-a11y', 'requirements': ['R1'],
                'steps': [{'action': 'audit_accessibility'}]}])
            self.assertFalse(report['functional_success'], report)
            rules = {f['rule'] for f in report['checks'][0]['accessibility_audits'][0]['findings']}
            self.assertTrue({'control-accessible-name', 'document-language', 'main-landmark'}.issubset(rules))
