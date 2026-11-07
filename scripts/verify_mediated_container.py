"""Actual container IPC checks; the host backend returns scripted text only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import os
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recursa.container_rlm import MEDIATED_SOURCE, run_mediated_fixture
from recursa.broker import OfflineBroker, ProviderBroker, PREFIX
from recursa.artifacts import validate_artifacts
from recursa.experiments import atomic_json
from recursa.processes import run_worker
from recursa.sandbox import run_python


def verify(output):
    with patch.dict(os.environ, {'RECURSA_CONTAINER_HOST_SENTINEL': 'host-only-offline-placeholder',
                                 'RECURSA_FIXTURE_PROVIDER_KEY': 'fixture-host-provider-key'}):
        return _verify(output)


def _verify(output):
    directory = Path(output)
    if directory.exists():
        raise ValueError('Use a fresh verification directory')
    directory.mkdir(parents=True)
    runtime = json.loads((ROOT / '.cache/rlm-runtime-image.json').read_text())
    cases = []
    for name, cap in [('host-completion-path', 2), ('host-budget-denial', 1)]:
        result = run_mediated_fixture(runtime['image_id'], directory / name, max_calls=cap)
        cases.append({'name': name, **result})
        atomic_json(directory / 'verification.json', {'status': 'in-progress', 'cases': cases, 'live_inference': False})
        assert result['container']['policy_verified'] and result['container']['cleanup_verified'], result
        assert result['broker']['scripted_dispatches'] == cap, result
        if cap == 2:
            assert result['status'] == 'completed' and result['artifact_count'] == 1, result
            assert [e.get('model') for e in result['broker']['events']] == ['scripted-root', 'scripted-sub'], result
        else:
            assert result['status'] == 'budget-exhausted' and result['artifact_count'] == 0, result
            assert result['broker']['events'][-1]['status'] == 'denied', result
    limits = {'max_calls': 2, 'max_output_tokens': 4096, 'max_input_bytes': 10000,
              'max_wall_seconds': 30, 'max_cost_usd': 0, 'max_depth': 1, 'max_concurrency': 1, 'max_repairs': 0}
    broker = OfflineBroker({'scripted-root': 'must not be dispatched'}, limits)
    payload = {'type': 'completion', 'id': 1, 'model': 'scripted-root', 'messages': [{'role': 'user', 'content': 'test'}], 'url': 'https://invalid.example'}
    source = 'import sys,json\nsys.__stdout__.write(' + repr(PREFIX.decode() + json.dumps(payload) + '\n') + ')\nsys.__stdout__.flush()\nreply=json.loads(sys.__stdin__.readline())\nassert reply["ok"] is False\n'
    container = run_python(source, runtime['image_id'], directory / 'invalid-request', broker=broker)
    assert container['status'] == 'completed' and container['cleanup_verified'], container
    assert broker.summary()['reserved_calls'] == 0 and broker.summary()['scripted_dispatches'] == 0
    cases.append({'name': 'invalid-request', 'container': container, 'broker': broker.summary()})
    # Intercept the HTTP transport in the actual supervised child process.
    # The fixture launcher substitutes the entire worker command before release.
    def intercepted_worker(command, payload, **options):
        assert command == [sys.executable, '-m', 'recursa.provider_worker']
        assert b'fixture-host-provider-key' not in payload
        fixture = ROOT / 'tests/fixtures/provider_worker.py'
        return run_worker([sys.executable, str(fixture)], payload, **options)

    with patch('recursa.provider_worker.run_worker', side_effect=intercepted_worker) as launch:
        for cap in (2, 1):
            config = {'base_url': 'https://recursa-fixture.invalid/v1', 'api_key_env': 'RECURSA_FIXTURE_PROVIDER_KEY',
                      'output_tokens': 2048, 'rates': {model: {'input_per_million': 1, 'output_per_million': 1}
                                                      for model in ('scripted-root', 'scripted-sub')},
                      'budget': {**limits, 'max_calls': cap, 'max_wall_seconds': 60,
                                 'max_input_bytes': 100000, 'max_cost_usd': 0.1}}
            case_dir = directory / f'supervised-{cap}'
            broker = ProviderBroker(config, case_dir / 'provider-private', authorize_live=True)
            container = run_python(MEDIATED_SOURCE, runtime['image_id'], case_dir / 'container',
                                   context={'max_calls': 2}, broker=broker, max_wall_seconds=45)
            assert container['status'] == 'completed' and container['policy_verified'] and container['cleanup_verified'], container
            stdout = (case_dir / 'container/private/stdout.bin').read_bytes()
            assert b'fixture-host-provider-key' not in stdout
            lines = [line for line in stdout.splitlines() if line and not line.startswith(PREFIX)]
            assert len(lines) == 1
            envelope = json.loads(lines[0])
            assert envelope['kind'] == 'offline-brokered-container' and envelope['live_inference'] is False
            assert envelope['host_sentinel_absent']
            run = envelope['run']
            artifacts = validate_artifacts({'artifacts': run['artifacts']}, {'R1'}) if run.get('artifacts') else []
            summary = broker.summary()
            assert summary['provider']['reserved_calls'] == cap
            assert launch.call_count == (2 if cap == 2 else 3)
            if cap == 2:
                assert len(artifacts) == 1 and run['status'] == 'completed'
                assert [event['model'] for event in summary['events']] == ['scripted-root', 'scripted-sub']
            else:
                assert not artifacts and summary['stop_reason'] == 'BudgetExceeded'
            for report in (case_dir / 'provider-private').rglob('*.json'):
                assert b'fixture-host-provider-key' not in report.read_bytes()
            cases.append({'name': f'supervised-{cap}', 'container': container, 'broker': summary,
                          'artifact_count': len(artifacts), 'live_inference': False,
                          'scope': 'Actual container and supervised worker with intercepted HTTP responses'})
    summary = {'status': 'passed', 'runtime_image': runtime, 'cases': cases, 'live_inference': False,
               'host_sentinel_set_for_verification': True,
               'verified_at': datetime.now(timezone.utc).isoformat(),
               'scope': 'Five actual container IPC fixtures, including two with intercepted supervised transport'}
    atomic_json(directory / 'verification.json', summary)
    print(json.dumps({'status': 'passed', 'cases': len(cases), 'live_inference': False}))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    verify(parser.parse_args().output)
