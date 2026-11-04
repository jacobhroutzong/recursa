"""Supervised host provider calls. No container, CLI batch or HTTP route uses this.

The worker is trusted host code, not a sandbox. Only explicit authorization can
create a session. Tests intercept HTTP inside a real lifetime-managed worker.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from recursa.experiments import atomic_json
from recursa.processes import run_worker
from recursa.provider import ProviderAdapter, ProviderFailure

ROOT = Path(__file__).resolve().parents[1]
RESULT_LIMIT = 500000
ERROR_CODES = frozenset({
    'InvalidRequest', 'RequestTooLarge', 'CredentialUnavailable', 'BudgetExceeded',
    'ProviderHTTPError', 'UnsupportedResponseEncoding', 'ResponseTooLarge',
    'IncompleteResponse', 'InvalidResponse', 'UsageUnavailable', 'InvalidUsage',
    'UsageExceededReservation', 'ProviderTransportOrResponseError',
})


class SupervisedProviderAdapter(ProviderAdapter):
    def __init__(self, config, output_dir, *, authorize_live=False):
        super().__init__(config, authorize_live=authorize_live)
        self._directory = Path(output_dir).resolve()
        self._directory.mkdir(parents=True, exist_ok=False)

    def complete(self, model, messages):
        # Serialize durable summaries with the same lock as reservations.
        with self._lock:
            try:
                return super().complete(model, messages)
            finally:
                try:
                    atomic_json(self._directory / 'session-report.json', self.summary())
                except Exception:
                    self._closed = 'ProviderRecordUnavailable'
                    raise ProviderFailure('ProviderRecordUnavailable') from None

    def _request(self, model, messages, key):
        # Parent complete() has already validated and reserved this request.
        # Never transmit the credential in stdin or persist it in a report.
        directory = self._directory / f'call-{self._budget.calls:06d}'
        directory.mkdir()
        atomic_json(directory / 'reservation.json', {
            'reserved_calls': self._budget.calls,
            'output_tokens_reserved': self._budget.output_reserved,
            'estimated_cost_committed_usd': self._budget.cost_reserved,
            'model': model,
            'prompt_sha256': hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest(),
            'status': 'reserved', 'billing_cost_usd': None,
            'scope': 'Host reservation before worker release; dispatch/charge may remain unknown',
        })
        config = deepcopy(self._config)
        config['budget'].update(max_calls=1, max_output_tokens=self._cap,
                                max_wall_seconds=self._budget.remaining())
        payload = json.dumps({'config': config, 'model': model, 'messages': messages,
                              'output': str(directory), 'authorize_live': True}, allow_nan=False).encode()
        try:
            report = run_worker([sys.executable, '-m', 'recursa.provider_worker'], payload,
                                timeout=self._budget.remaining(), cwd=ROOT)
        except BaseException as error:
            code = 'ProviderCancelled' if isinstance(error, KeyboardInterrupt) else 'ProviderWorkerUnavailable'
            self._closed = code
            atomic_json(directory / 'worker-report.json', {
                'status': 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed',
                'error_classification': code, 'provider_dispatch_possible': True,
                'billing_cost_usd': None, 'reservation_retained': True,
            })
            if isinstance(error, KeyboardInterrupt):
                raise
            raise ProviderFailure(code) from None
        report.pop('live_inference', None)  # Generic worker metadata cannot determine inference.
        report.update(provider_dispatch_possible=True, billing_cost_usd=None, reservation_retained=True)
        atomic_json(directory / 'worker-report.json', report)
        if report['status'] != 'complete':
            raise ProviderFailure('ProviderWorkerTimeout' if report['status'] == 'timeout' else 'ProviderWorkerFailed')
        result_path = directory / 'response.json'
        if not result_path.is_file() or result_path.stat().st_size > RESULT_LIMIT:
            raise ProviderFailure('InvalidWorkerResult')
        result = json.loads(result_path.read_bytes())
        if not isinstance(result, dict) or type(result.get('ok')) is not bool:
            raise ProviderFailure('InvalidWorkerResult')
        if not result['ok']:
            code = result.get('error_classification')
            raise ProviderFailure(code if isinstance(code, str) and code in ERROR_CODES else 'ProviderWorkerFailed')
        if set(result) != {'ok', 'text', 'usage'}:
            raise ProviderFailure('InvalidWorkerResult')
        # The parent repeats response/usage checks and accounting independently.
        return {'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': result['text']}}], 'usage': result['usage']}

    def summary(self):
        result = super().summary()
        result['mode'] = 'supervised-host-provider-adapter'
        return result


def main():
    raw = sys.stdin.buffer.read(500001)
    if len(raw) > 500000:
        return 2
    payload = json.loads(raw)
    if (not isinstance(payload, dict) or set(payload) != {'config', 'model', 'messages', 'output', 'authorize_live'}
            or payload['authorize_live'] is not True):
        return 2
    directory = Path(payload['output'])
    if not directory.is_dir():
        return 2
    adapter = ProviderAdapter(payload['config'], authorize_live=True)
    try:
        text = adapter.complete(payload['model'], payload['messages'])
        usage = adapter.summary()['events'][-1]['provider_reported_usage']
        result = {'ok': True, 'text': text, 'usage': usage}
    except ProviderFailure as error:
        code = str(error)
        result = {'ok': False, 'error_classification': code if code in ERROR_CODES else 'ProviderWorkerFailed'}
    # Text is private. No raw request/endpoint/headers or provider error body is saved.
    atomic_json(directory / 'response.json', result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
