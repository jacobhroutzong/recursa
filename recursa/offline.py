"""One-command, human-authored application fixture verification. No inference."""
import argparse
import json
from pathlib import Path

from recursa.pipeline import verify_application
from recursa.budget import BudgetExceeded

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    spec = json.loads((ROOT / 'examples/specs/tasks.json').read_text(encoding='utf-8'))
    folder = ROOT / 'examples/fixtures/task-app'
    ids = [r['id'] for r in spec['requirements']]
    artifacts = [{'path': p.relative_to(folder).as_posix(), 'content': p.read_text(encoding='utf-8'), 'requirements': ids}
                 for p in sorted(folder.rglob('*')) if p.suffix in {'.html', '.ts', '.css'}]
    scenarios = json.loads((folder / 'scenarios.json').read_text(encoding='utf-8'))
    return spec, artifacts, scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh output directory')
    parser.add_argument('--max-wall-seconds', type=float, default=180, help='Shared verification deadline (default: 180 seconds)')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory to preserve earlier evidence')
    spec, artifacts, scenarios = fixture()
    unit_cases = json.loads((ROOT / 'examples/fixtures/task-app/unit-cases.json').read_text(encoding='utf-8'))
    try:
        result = verify_application(spec, artifacts, args.output, scenarios=scenarios,
                                   typescript_directory=ROOT / 'tooling/typecheck/node_modules/typescript',
                                   unit_cases=unit_cases, max_wall_seconds=args.max_wall_seconds)
    except BudgetExceeded:
        print(json.dumps({'status': 'budget-exhausted', 'report': str(args.output.resolve() / 'application-report.json')}))
        return 1
    print(json.dumps({'provenance': 'human-authored engineering fixture; no model inference',
                      'status': result['status'], 'build_success': result['verification']['build_success'],
                      'functional_success': result['verification']['functional_success'],
                      'lint_success': result['verification']['lint_success'],
                      'unit_test_pass_rate': result['verification']['unit_test_pass_rate'],
                      'accessibility_success': result['verification']['accessibility_success'],
                      'report': str(args.output.resolve() / 'application-report.json')}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
