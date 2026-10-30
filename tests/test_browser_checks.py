import tempfile
import unittest
from pathlib import Path

from recursa.browser_checks import check_application, validate_scenarios
from recursa.build import build_application
from recursa.offline import fixture


class BrowserChecksTests(unittest.TestCase):
    def test_rejects_code_selectors_unknown_roles_and_unbounded_scenarios(self):
        for target in ({'selector': 'body'}, {'role': 'invented'}, {'test_id': ''}):
            with self.assertRaises(ValueError):
                validate_scenarios([{'id': 'bad', 'requirements': ['R1'], 'steps': [{'action': 'click', 'target': target}]}])
        with self.assertRaises(ValueError):
            validate_scenarios([])

    def test_missing_tools_remain_unmeasured(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'index.html').write_text('<html></html>')
            _, _, scenarios = fixture()
            report = check_application(tmp, scenarios, tool_directory=Path(tmp) / 'missing')
            self.assertEqual(report['status'], 'unavailable')
            self.assertIsNone(report['functional_success'])

    def test_actual_browser_blocks_external_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = [
                {'path': 'index.html', 'content': '<script type="module" src="main.js"></script><h1>Fixture</h1>', 'requirements': ['R1']},
                {'path': 'main.js', 'content': 'fetch("https://invalid.example/forbidden").catch(()=>{});', 'requirements': ['R1']}]
            build = build_application(artifacts, tmp)
            self.assertTrue(build['build_success'], build)
            report = check_application(build['dist_path'], [{'id': 'blocked', 'requirements': ['R1'], 'source_path': 'main.js',
                'steps': [{'action': 'expect_visible', 'target': {'role': 'heading', 'name': 'Fixture'}}]}])
            self.assertFalse(report['functional_success'], report)
            self.assertTrue(report['checks'][0]['blocked_activity'])
