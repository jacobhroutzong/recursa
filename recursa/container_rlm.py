"""Contained official-RLM runtime and scripted verification fixtures."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import threading

from recursa.artifacts import save_artifacts, validate_artifacts
from recursa.broker import FRAME_LIMIT, PREFIX, ProviderBroker
from recursa.engine import validate_spec
from recursa.experiments import atomic_json
from recursa.sandbox import run_python

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "from recursa.container_rlm import scripted_fixture; import json; print(json.dumps(scripted_fixture(context)))"
MEDIATED_SOURCE = "from recursa.container_rlm import mediated_fixture; import json; print(json.dumps(mediated_fixture(context)))"
REVIEWED_SOURCE = "from recursa.container_rlm import reviewed_completion; reviewed_completion(context)"
_wire_lock = threading.RLock()
_wire_id = 0


def runtime_source_hash():
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'recursa').glob('*.py')):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update((ROOT / 'requirements-live.lock').read_bytes())
    return digest.hexdigest()


def scripted_fixture(options):
    return _fixture(options, mediated=False)


def mediated_fixture(options):
    return _fixture(options, mediated=True)


def wire_completion(model, messages):
    from recursa.budget import BudgetExceeded
    global _wire_id
    with _wire_lock:
        _wire_id += 1
        frame = {'type': 'completion', 'id': _wire_id, 'model': model, 'messages': messages}
        encoded = json.dumps(frame).encode()
        if len(encoded) > FRAME_LIMIT:
            raise ValueError('Request frame too large')
        sys.__stdout__.write(PREFIX.decode() + encoded.decode() + '\n')
        sys.__stdout__.flush()
        raw = sys.__stdin__.readline(FRAME_LIMIT + 2)
        if not raw.endswith('\n') or len(raw.encode()) > FRAME_LIMIT + 1:
            raise ValueError('Invalid broker reply')
        response = json.loads(raw)
        if response.get('type') != 'completion-result' or response.get('id') != _wire_id:
            raise ValueError('Mismatched broker reply')
        if response.get('ok') is not True:
            if response.get('error') == 'BudgetExceeded':
                raise BudgetExceeded('Host budget exhausted')
            raise ValueError('Host rejected completion request')
        if set(response) != {'type', 'id', 'ok', 'text'} or not isinstance(response['text'], str):
            raise ValueError('Invalid completion reply')
        return response['text']


def _fixture(options, *, mediated):
    """Runs only under the container bootstrap with intercepted HTTP transport."""
    import httpx
    import openai
    from unittest.mock import patch
    from recursa.live import run_live
    if not isinstance(options, dict) or set(options) != {'max_calls'} or type(options['max_calls']) is not int or not 1 <= options['max_calls'] <= 3:
        raise ValueError('Only bounded scripted fixtures are accepted')
    if os.environ.get('RECURSA_CONTAINER_HOST_SENTINEL'):
        raise ValueError('Host sentinel must not enter container')
    sentinel = 'EXTERNAL_SPEC_SENTINEL_CONTAINER_5381'
    spec = {'name': 'Scripted container integration fixture', 'requirements': [
        {'id': 'R1', 'text': sentinel + ': reject blank task titles'}]}
    manifest = {'artifacts': [{'path': 'src/title.ts', 'requirements': ['R1'],
        'content': 'export const titleValid = (value: string): boolean => value.trim().length > 0;'}]}
    original = openai.OpenAI
    seen = []
    def transport(request):
        body = json.loads(request.content)
        seen.append(body['model'])
        if body['model'] == 'scripted-root':
            assert sentinel not in json.dumps(body['messages'])
            content = scripted_responses()['scripted-root']
        else:
            assert body['model'] == 'scripted-sub' and sentinel in json.dumps(body['messages'])
            content = json.dumps(manifest)
        if mediated:
            content = wire_completion(body['model'], body['messages'])
        return httpx.Response(200, json={'id': 'scripted-container', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 30, 'total_tokens': 50}})
    def factory(**kwargs):
        return original(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    config = {'trusted_local_execution': True, 'models': {'root': 'scripted-root', 'sub': 'scripted-sub'},
        'provider': {'base_url': 'http://127.0.0.1:9999/v1', 'api_key_env': 'RECURSA_OFFLINE_ONLY_KEY'},
        'rates': {name: {'input_per_million': 0, 'output_per_million': 0} for name in ('scripted-root', 'scripted-sub')},
        'max_iterations': 2, 'per_call_output_tokens': 2048,
        'budget': {'max_calls': options['max_calls'], 'max_output_tokens': 6144, 'max_input_bytes': 100000,
                   'max_wall_seconds': 30, 'max_cost_usd': 0, 'max_depth': 1, 'max_concurrency': 1, 'max_repairs': 0}}
    with tempfile.TemporaryDirectory(dir='/work') as tmp, open('/work/upstream-private.log', 'w') as log, redirect_stdout(log), redirect_stderr(log), patch.dict(os.environ, {'RECURSA_OFFLINE_ONLY_KEY': 'offline-placeholder'}), patch('openai.OpenAI', side_effect=factory):
        run = run_live(spec, Path(tmp), config, authorize_live=True)
    mode = 'offline-brokered-container' if mediated else 'offline-scripted-container'
    run.update(mode=mode, label='Scripted official RLM container fixture', live_inference=False)
    return {'kind': mode, 'live_inference': False,
            'transport_models': seen, 'host_sentinel_absent': True, 'run': run}


def reviewed_completion(options):
    """Forward the pinned runtime's model requests through the host pipe."""
    import httpx
    import openai
    from unittest.mock import patch
    from recursa.live import run_live

    spec, config = options['spec'], options['config']
    original = openai.OpenAI

    def transport(request):
        body = json.loads(request.content)
        content = wire_completion(body['model'], body['messages'])
        return httpx.Response(200, json={
            'id': 'host-pipe', 'object': 'chat.completion', 'created': 0, 'model': body['model'],
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
            # The SDK requires usage fields. Only the host has provider-reported usage.
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
        })

    def factory(**kwargs):
        return original(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(transport)))

    with (tempfile.TemporaryDirectory(dir='/work') as tmp, open(os.devnull, 'w') as log,
          redirect_stdout(log), redirect_stderr(log),
          patch.dict(os.environ, {'RECURSA_PIPE_PLACEHOLDER': 'container-placeholder'}),
          patch('openai.OpenAI', side_effect=factory)):
        run = run_live(spec, Path(tmp), config, authorize_live=True)
    envelope = {'kind': 'reviewed-spec-result', 'status': run['status'], 'artifacts': run['artifacts'],
                'context_reported': any(event['type'] == 'context' for event in run['events']),
                'subcall_reported': any(event['type'] == 'subcall' and event['status'] == 'completed'
                                        for event in run['events'])}
    encoded = json.dumps(envelope, allow_nan=False)
    if len(encoded.encode()) > FRAME_LIMIT:
        encoded = json.dumps({'kind': 'reviewed-spec-result', 'status': 'result-too-large',
                              'artifacts': [], 'context_reported': None, 'subcall_reported': None})
    sys.__stdout__.write(encoded + '\n')
    sys.__stdout__.flush()


def _reviewed_result(stdout, requirement_ids):
    lines = [line for line in stdout.split(b'\n') if line and not line.startswith(PREFIX)]
    if len(lines) != 1 or len(lines[0]) > FRAME_LIMIT:
        raise ValueError('Expected one bounded result')
    data = json.loads(lines[0])
    if (not isinstance(data, dict)
            or set(data) != {'kind', 'status', 'artifacts', 'context_reported', 'subcall_reported'}
            or data['kind'] != 'reviewed-spec-result'
            or data['status'] not in {'completed', 'incomplete-evidence', 'verification-failed',
                                      'budget-exhausted', 'failed', 'result-too-large'}
            or not isinstance(data['artifacts'], list)
            or any(value is not None and type(value) is not bool
                   for value in (data['context_reported'], data['subcall_reported']))):
        raise ValueError('Invalid contained result')
    artifacts = validate_artifacts({'artifacts': data['artifacts']}, requirement_ids) if data['artifacts'] else []
    return data, artifacts


def run_reviewed(spec, config, image, output_dir, *, authorize_live=False, runtime_record=None):
    """Run a reviewed specification through the contained RLM with a host provider."""
    if authorize_live is not True:
        raise ValueError('Contained provider execution requires explicit authorization')
    validate_spec(spec)
    if len(json.dumps(spec, allow_nan=False).encode()) > 200000:
        raise ValueError('Reviewed specification exceeds 200000 bytes')
    required = {'models', 'provider', 'rates', 'budget', 'per_call_output_tokens', 'max_iterations'}
    if (not isinstance(config, dict) or not required <= config.keys()
            or config.keys() - required - {'name', 'spec', 'mode', 'trials', 'trusted_local_execution'}
            or config.get('trusted_local_execution', False) is not False):
        raise ValueError('Use a contained synthesis configuration')
    models = config['models']
    if (not isinstance(models, dict) or set(models) != {'root', 'sub'}
            or any(not isinstance(model, str) or not model.strip() for model in models.values())):
        raise ValueError('Configure root and sub models')
    provider, limits, rates = config['provider'], config['budget'], config['rates']
    if (not isinstance(provider, dict) or set(provider) != {'base_url', 'api_key_env'}
            or not isinstance(rates, dict) or set(rates) != set(models.values())):
        raise ValueError('Configure a fixed provider and pricing for the selected models')
    budget_fields = {'max_calls', 'max_output_tokens', 'max_input_bytes', 'max_wall_seconds',
                     'max_cost_usd', 'max_depth', 'max_concurrency', 'max_repairs'}
    if (not isinstance(limits, dict) or set(limits) != budget_fields or limits['max_repairs'] != 0
            or type(limits.get('max_calls')) is not int or not 1 <= limits['max_calls'] <= 64
            or type(limits.get('max_wall_seconds')) not in (int, float) or not 0 < limits['max_wall_seconds'] <= 120
            or type(config['max_iterations']) is not int or not 1 <= config['max_iterations'] <= 32):
        raise ValueError('Contained synthesis requires bounded calls, wall time and iterations, with zero repairs')
    _validate_runtime_image(image, runtime_record)
    directory = Path(output_dir).resolve()
    if directory.exists():
        raise ValueError('Use a fresh output directory')
    broker = ProviderBroker({**provider, 'rates': rates, 'budget': limits,
                             'output_tokens': config['per_call_output_tokens']},
                            directory / 'private/provider', authorize_live=True)
    child_config = {'trusted_local_execution': True, 'models': models,
                    'provider': {'base_url': 'http://127.0.0.1:9999/v1', 'api_key_env': 'RECURSA_PIPE_PLACEHOLDER'},
                    'rates': {model: {'input_per_million': 0, 'output_per_million': 0} for model in rates},
                    'budget': {**limits, 'max_cost_usd': 0},
                    'max_iterations': config['max_iterations'], 'per_call_output_tokens': config['per_call_output_tokens']}
    # The host enforces the live call cap. The local copy permits the first
    # over-cap request to reach the broker so the denial is recorded there.
    child_config['budget']['max_calls'] += 1
    child_config['budget']['max_output_tokens'] += config['per_call_output_tokens']
    sandbox_dir = directory / 'private/container'
    container = run_python(REVIEWED_SOURCE, image, sandbox_dir, context={'spec': spec, 'config': child_config},
                           broker=broker, max_wall_seconds=limits['max_wall_seconds'])
    report = {'status': 'container-failed', 'mode': 'contained-reviewed-spec', 'live_inference': None,
              'artifact_count': 0, 'functional_success': None, 'context_reported': None, 'subcall_reported': None,
              'spec_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
              'container': container, 'broker': broker.summary()}
    if container['status'] == 'completed' and container['policy_verified'] and container['cleanup_verified']:
        try:
            stdout = (sandbox_dir / 'private/stdout.bin').read_bytes()
            data, artifacts = _reviewed_result(stdout, {r['id'] for r in spec['requirements']})
        except (ValueError, TypeError, OSError, RecursionError):
            report['status'] = 'invalid-result'
        else:
            report.update(status=data['status'], context_reported=data['context_reported'],
                          subcall_reported=data['subcall_reported'])
            if broker.closed_reason:
                report['status'] = 'budget-exhausted' if broker.closed_reason == 'BudgetExceeded' else 'broker-rejected'
            if report['status'] == 'completed':
                if (not artifacts or data['context_reported'] is not True or data['subcall_reported'] is not True
                        or sum(event['status'] == 'completed' for event in report['broker']['events']) < 2):
                    report['status'] = 'incomplete-evidence'
                else:
                    save_artifacts(directory / 'artifacts', artifacts)
                    report.update(status='source-returned', artifact_count=len(artifacts))
    atomic_json(directory / 'reviewed-report.json', report)
    return report


def scripted_responses():
    root = '''```repl
import json
rows = read_requirements(["R1"])
set_task_plan([{"id":"contract","label":"Scripted title contract","kind":"contract","requirements":["R1"]}])
begin_task("contract")
draft = llm_query("Return the scripted artifact for " + json.dumps(rows))
saved = submit_task_output("contract", json.loads(draft))
answer["content"] = json.dumps({"artifact_paths": saved["artifact_paths"]})
answer["ready"] = True
```'''
    manifest = {'artifacts': [{'path': 'src/title.ts', 'requirements': ['R1'],
        'content': 'export const titleValid = (value: string): boolean => value.trim().length > 0;'}]}
    return {'scripted-root': root, 'scripted-sub': json.dumps(manifest)}


def _validate_runtime_image(image, runtime_record):
    record = runtime_record if runtime_record is not None else json.loads((ROOT / '.cache/rlm-runtime-image.json').read_text(encoding='utf-8'))
    if (record.get('image_id') != image or record.get('runtime_source_sha256') != runtime_source_hash()
            or record.get('platform') != 'linux/amd64'):
        raise ValueError('Runtime image does not match current source; rebuild with scripts/build_rlm_image.py')


def run_fixture(image, output_dir, *, max_calls=2, runtime_record=None):
    """Parent accepts fixed offline fixture output, never executes returned code."""
    if type(max_calls) is not int or not 1 <= max_calls <= 3:
        raise ValueError('Fixture call budget must be 1–3')
    _validate_runtime_image(image, runtime_record)
    directory = Path(output_dir)
    report = run_python(SOURCE, image, directory, context={'max_calls': max_calls}, max_wall_seconds=60)
    if report['status'] != 'completed' or not report['policy_verified'] or not report['cleanup_verified']:
        return {'status': 'container-failed', 'container': report, 'live_inference': False}
    data = json.loads((directory / 'private/stdout.bin').read_text(encoding='utf-8'))
    if data.get('kind') != 'offline-scripted-container' or data.get('live_inference') is not False:
        raise ValueError('Invalid fixture output envelope')
    run = data['run']
    if run.get('mode') != 'offline-scripted-container' or run.get('live_inference') is not False:
        raise ValueError('Container output must preserve fixture provenance')
    # Treat all returned container bytes as untrusted, even in this owned fixture.
    artifacts = validate_artifacts({'artifacts': run['artifacts']}, {'R1'}) if run.get('artifacts') else []
    if artifacts:
        save_artifacts(directory / 'artifacts', artifacts)
    safe = {'status': run['status'], 'live_inference': False, 'mode': 'offline-scripted-container',
            'artifact_count': len(artifacts), 'transport_models': data['transport_models'],
            'model_calls': run.get('metrics', {}).get('model_calls'),
            'context_observed': any(e.get('type') == 'context' for e in run.get('events', [])),
            'subcall_observed': any(e.get('type') == 'subcall' and e.get('status') == 'completed' for e in run.get('events', [])),
            'container': report, 'scope': 'Scripted integration only; token usage is fixture data, not research evidence'}
    atomic_json(directory / 'fixture-report.json', safe)
    return safe


def run_mediated_fixture(image, output_dir, *, max_calls=2, runtime_record=None):
    from recursa.broker import OfflineBroker, PREFIX
    if type(max_calls) is not int or not 1 <= max_calls <= 2:
        raise ValueError('Host fixture budget must be 1–2')
    _validate_runtime_image(image, runtime_record)
    limits = {'max_calls': max_calls, 'max_output_tokens': 4096, 'max_input_bytes': 100000,
              'max_wall_seconds': 60, 'max_cost_usd': 0, 'max_depth': 1, 'max_concurrency': 1, 'max_repairs': 0}
    broker = OfflineBroker(scripted_responses(), limits)
    directory = Path(output_dir)
    # The child always has room for two calls; only the HOST cap changes here.
    container = run_python(MEDIATED_SOURCE, image, directory, context={'max_calls': 2}, broker=broker, max_wall_seconds=60)
    if container['status'] != 'completed' or not container['policy_verified'] or not container['cleanup_verified']:
        return {'status': 'container-failed', 'container': container, 'broker': broker.summary(), 'live_inference': False}
    lines = [line for line in (directory / 'private/stdout.bin').read_bytes().splitlines() if line and not line.startswith(PREFIX)]
    if len(lines) != 1:
        raise ValueError('Expected one bounded final fixture envelope')
    data = json.loads(lines[0])
    run = data['run']
    if (data.get('kind') != 'offline-brokered-container' or data.get('live_inference') is not False
            or run.get('mode') != 'offline-brokered-container' or run.get('live_inference') is not False):
        raise ValueError('Fixture provenance mismatch')
    artifacts = validate_artifacts({'artifacts': run['artifacts']}, {'R1'}) if run.get('artifacts') else []
    if artifacts:
        save_artifacts(directory / 'artifacts', artifacts)
    status = 'budget-exhausted' if broker.budget.stop_reason else 'broker-rejected' if broker.closed_reason else run['status']
    summary = {'status': status, 'mode': 'offline-brokered-container', 'live_inference': False,
               'artifact_count': len(artifacts), 'broker': broker.summary(), 'container': container,
               'scope': 'Host-observed scripted completions through bounded pipes; no real provider inference'}
    atomic_json(directory / 'fixture-report.json', summary)
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run a reviewed specification with a contained RLM and authorized host provider.')
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--authorize-live', action='store_true', required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    config = json.loads(args.config.read_text(encoding='utf-8'))
    report = run_reviewed(spec, config, args.image, args.output, authorize_live=args.authorize_live)
    print(json.dumps({'status': report['status'], 'artifact_count': report['artifact_count']}))
    return 0 if report['status'] == 'source-returned' else 1


if __name__ == '__main__':
    raise SystemExit(main())
