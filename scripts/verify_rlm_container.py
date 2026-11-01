"""Run two actual contained-RLM fixtures, with scripted transport only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.container_rlm import run_fixture
from recursa.experiments import atomic_json


def verify(output):
    record = json.loads((ROOT / '.cache/rlm-runtime-image.json').read_text(encoding='utf-8'))
    directory = Path(output)
    if directory.exists():
        raise ValueError('Use a fresh output directory')
    directory.mkdir(parents=True)
    cases = []
    for name, budget in [('inspection-subcall-artifact', 2), ('budget-exhaustion', 1)]:
        result = run_fixture(record['image_id'], directory / name, max_calls=budget)
        cases.append({'name': name, **result})
        atomic_json(directory / 'verification.json', {'runtime_image': record, 'cases': cases, 'status': 'in-progress', 'live_inference': False})
        assert result['container']['policy_verified'] and result['container']['cleanup_verified'], result
        assert result['context_observed'], result
        if budget == 2:
            assert result['status'] == 'completed' and result['artifact_count'] == 1 and result['subcall_observed'], result
            assert result['transport_models'] == ['scripted-root', 'scripted-sub'], result
        else:
            assert result['status'] == 'budget-exhausted' and result['artifact_count'] == 0 and not result['subcall_observed'], result
            assert result['transport_models'] == ['scripted-root'], result
    summary = {'runtime_image': record, 'cases': cases, 'status': 'passed', 'live_inference': False,
               'verified_at': datetime.now(timezone.utc).isoformat(),
               'scope': 'Two actual official-RLM container fixtures with scripted HTTP responses, not genuine inference'}
    atomic_json(directory / 'verification.json', summary)
    print(json.dumps({'status': summary['status'], 'cases': len(cases), 'live_inference': False}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    verify(parser.parse_args().output)
