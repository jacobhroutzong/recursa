"""Offline application worker. No provider execution mode is implemented."""
import json
from pathlib import Path
import sys

from recursa.experiments import atomic_json
from recursa.processes import run_worker

ROOT = Path(__file__).resolve().parents[1]


def run_offline_application(output_dir, *, max_wall_seconds=180):
    directory = Path(output_dir).resolve()
    if directory.exists():
        raise ValueError('Use a fresh output directory')
    payload = json.dumps({'output': str(directory / 'application'), 'max_wall_seconds': max_wall_seconds}, allow_nan=False).encode()
    directory.mkdir(parents=True)
    try:
        report = run_worker([sys.executable, '-m', 'recursa.worker'], payload,
                            timeout=max_wall_seconds, cwd=ROOT)
    except BaseException as error:
        atomic_json(directory / 'worker-report.json', {'status': 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed',
                    'error_classification': type(error).__name__, 'live_inference': False})
        raise
    atomic_json(directory / 'worker-report.json', report)
    return report


def main():
    # Module imports above are trusted; workload begins only after the parent
    # has attached the worker to the lifetime boundary and releases stdin.
    raw = sys.stdin.buffer.read(500001)
    if len(raw) > 500000:
        return 2
    config = json.loads(raw)
    if not isinstance(config, dict) or set(config) != {'output', 'max_wall_seconds'}:
        return 2
    from recursa.offline import fixture
    from recursa.pipeline import verify_application
    from recursa.budget import BudgetExceeded
    spec, artifacts, scenarios = fixture()
    cases = json.loads((ROOT / 'examples/fixtures/task-app/unit-cases.json').read_text(encoding='utf-8'))
    try:
        result = verify_application(spec, artifacts, config['output'], scenarios=scenarios, unit_cases=cases,
                                    max_wall_seconds=config['max_wall_seconds'],
                                    typescript_directory=ROOT / 'tooling/typecheck/node_modules/typescript')
    except BudgetExceeded:
        return 1
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
