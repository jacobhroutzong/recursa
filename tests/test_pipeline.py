from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from recursa.offline import ROOT, fixture
from recursa.pipeline import verify_application


class ApplicationPipelineTests(unittest.TestCase):
    def test_real_build_browser_and_repair_of_broken_behavior(self):
        spec, artifacts, scenarios = fixture()
        original = next(a for a in artifacts if a['path'] == 'src/main.ts')
        broken = deepcopy(artifacts)
        source = next(a for a in broken if a['path'] == 'src/main.ts')
        self.assertIn('completed: false', source['content'])
        source['content'] = source['content'].replace('completed: false', 'completed: true')
        contexts = []

        def scripted_repair(context):
            contexts.append(context)
            return {'artifacts': [original]}

        with tempfile.TemporaryDirectory() as tmp:
            report = verify_application(spec, broken, tmp, scenarios=scenarios,
                typescript_directory=ROOT / 'tooling/typecheck/node_modules/typescript',
                repair_callback=scripted_repair, max_repairs=1)
            self.assertEqual(report['status'], 'passed', report['verification'])
            self.assertEqual(report['repair_status'], 'rechecked')
            self.assertEqual(report['repair_attempts'], 1)
            self.assertEqual(report['verification_passes'], 2)
            self.assertEqual(contexts[0]['allowed_paths'], ['src/main.ts'])
            self.assertTrue(report['verification']['typecheck_success'])
            self.assertTrue(report['verification']['build_success'])
            self.assertTrue(report['verification']['functional_success'])
            self.assertIsNone(report['coverage']['satisfaction_rate'])
            self.assertTrue(Path(tmp, 'application-report.json').exists())

    def test_unavailable_tools_cannot_count_as_success(self):
        spec, artifacts, scenarios = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_application(spec, artifacts, tmp, scenarios=scenarios,
                                        frontend_tools=Path(tmp) / 'missing')
            self.assertEqual(result['status'], 'incomplete')
            self.assertIsNone(result['verification']['functional_success'])
            self.assertIsNone(result['verification']['build_success'])

    def test_unknown_scenario_references_and_unbudgeted_repairs_rejected(self):
        spec, artifacts, scenarios = fixture()
        scenarios[0]['requirements'] = ['UNKNOWN']
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                verify_application(spec, artifacts, tmp, scenarios=scenarios)
            with self.assertRaises(ValueError):
                verify_application(spec, artifacts, tmp, max_repairs=1)
