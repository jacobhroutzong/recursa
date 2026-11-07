"""Package public specification replays and the verified reference screenshot."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recursa.engine import run_smoke
from recursa.offline import fixture
from recursa.experiments import atomic_json


def build(report_path):
    studio = ROOT / 'apps/studio'
    presets = []
    for filename, size in [('tasks', 'Small'), ('operations', 'Medium'), ('aviation', 'Large')]:
        spec = json.loads((ROOT / f'examples/specs/{filename}.json').read_text(encoding='utf-8'))
        presets.append({'key': filename, 'size': size, 'replay': run_smoke(spec)})

    report = json.loads(report_path.read_text(encoding='utf-8'))
    verification = report['verification']
    _, artifacts, _ = fixture()
    expected = {item['path']: item['content'] for item in artifacts}
    measured = {item['path']: item['content'] for item in report['artifacts']}
    if report['status'] != 'passed' or verification['functional_success'] is not True or measured != expected:
        raise ValueError('Use a passing verification report for the current Task Management fixture')
    screenshot = (studio / 'assets/task-preview.png').read_bytes()
    if not screenshot.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Capture the verified Task Management screenshot first')
    metrics = {key: verification[key] for key in (
        'build_success', 'functional_success', 'lint_success', 'unit_test_pass_rate',
        'accessibility_success', 'end_to_end_pass_rate')}
    metrics['model_calls'] = 0
    metrics['requirement_satisfaction'] = None
    reference = {
        'schema_version': 1, 'id': 'reference-task-management', 'label': 'Task Management · Reference app',
        'mode': 'human-authored-reference', 'status': 'verified', 'live_inference': False,
        'events': [
            {'id': 'fixture', 'type': 'context', 'label': 'Load the Task Management reference source',
             'status': 'completed', 'details': {'provenance': 'Human-authored reference application'}},
            {'id': 'verification', 'parent_id': 'fixture', 'type': 'validation', 'label': 'Verify the built application',
             'status': 'completed', 'details': metrics},
            {'id': 'capture', 'parent_id': 'verification', 'type': 'artifact', 'label': 'Capture the verified reference build',
             'status': 'completed', 'details': {'screenshot_sha256': hashlib.sha256(screenshot).hexdigest()}},
        ],
        'artifacts': artifacts, 'metrics': metrics,
    }
    atomic_json(studio / 'playground.json', {'presets': presets, 'reference': reference})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    build(parser.parse_args().report)
