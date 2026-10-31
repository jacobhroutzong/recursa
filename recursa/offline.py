"""One-command, human-authored application fixture verification. No inference."""
import argparse
import json
from pathlib import Path


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
    from recursa.worker import run_offline_application
    worker = run_offline_application(args.output, max_wall_seconds=args.max_wall_seconds)
    report_path = args.output.resolve() / 'application/application-report.json'
    result = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    measured = result.get('verification', {})
    print(json.dumps({'provenance': 'human-authored engineering fixture; no model inference',
                      'status': result.get('status', 'failed') if worker['status'] == 'complete' else worker['status'], 'worker_status': worker['status'],
                      'build_success': measured.get('build_success'),
                      'functional_success': measured.get('functional_success'),
                      'lint_success': measured.get('lint_success'),
                      'unit_test_pass_rate': measured.get('unit_test_pass_rate'),
                      'accessibility_success': measured.get('accessibility_success'),
                      'worker_report': str(args.output.resolve() / 'worker-report.json'),
                      'report': str(report_path) if report_path.exists() else None}, indent=2))
    return 0 if worker['status'] == 'complete' and result.get('status') == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
