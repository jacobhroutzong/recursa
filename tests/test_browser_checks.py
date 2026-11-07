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

    def test_csv_assertion_checks_escaped_fields_and_leaves_ordinary_downloads_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'index.html').write_text('<button>Export CSV</button><p role="status"></p><script src="app.js"></script>')
            script = '''document.querySelector('button').onclick=()=>{
              const a=document.createElement('a');
              a.href=URL.createObjectURL(new Blob(['id,note\\r\\nN3,"Rush, ""fragile"""\\r\\n']));
              a.download='orders.csv';a.click();
              setTimeout(()=>document.querySelector('p').textContent='Export attempted',100);
            };'''
            (directory / 'app.js').write_text(script)
            target = {'role': 'button', 'name': 'Export CSV'}
            approved = {'action': 'expect_csv_download', 'target': target,
                        'rows': [['id', 'note'], ['N3', 'Rush, "fragile"']]}
            scenarios = [
                {'id': 'reviewed', 'requirements': ['R1'], 'steps': [approved]},
                {'id': 'ordinary', 'requirements': ['R1'], 'steps': [
                    {'action': 'click', 'target': target},
                    {'action': 'expect_text', 'target': {'role': 'status'}, 'value': 'Export attempted'},
                ]},
            ]
            report = check_application(directory, scenarios)
            self.assertEqual([row['status'] for row in report['checks']], ['passed', 'failed'], report)
            self.assertIn('download-blocked', report['checks'][1]['blocked_activity'])
            (directory / 'app.js').write_text(script.replace('"Rush, ""fragile"""', 'Rush, fragile'))
            invalid = check_application(directory, scenarios[:1])
            self.assertEqual(invalid['status'], 'failed', invalid)
            self.assertEqual(invalid['checks'][0]['blocked_activity'], [])
