"""Explicitly authorized host-only HTTP adapter; not wired to any runner/server.

Tests use an intercepted transport. Import and configuration perform no I/O.
Reservations and provider-reported usage are estimates, never billing evidence.
"""
from copy import deepcopy
import hashlib
import json
import os
import re
import threading
from urllib.parse import urlsplit

from recursa.budget import BudgetExceeded, CallBudget


class ProviderFailure(RuntimeError):
    """Classification only: never propagate provider bodies or credentials."""


class ProviderAdapter:
    def __init__(self, config, *, authorize_live=False):
        if authorize_live is not True:
            raise ValueError('Explicit live authorization required')
        if not isinstance(config, dict) or set(config) != {
                'base_url', 'api_key_env', 'rates', 'budget', 'output_tokens'}:
            raise ValueError('Fixed host provider configuration required')
        config = deepcopy(config)
        url = config['base_url']
        if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
            raise ValueError('Invalid endpoint')
        try:
            parts = urlsplit(url)
            parts.port  # Validate a supplied port without resolving the hostname.
        except ValueError:
            raise ValueError('Invalid endpoint') from None
        if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or '\\' in url or
                (parts.scheme == 'http' and parts.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('HTTPS or loopback HTTP endpoint required')
        if not isinstance(config['api_key_env'], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', config['api_key_env']):
            raise ValueError('Credential environment variable name required')
        cap = config['output_tokens']
        if type(cap) is not int or not 1 <= cap <= 65536:
            raise ValueError('Bounded output reservation required')
        budget = CallBudget(config['budget'], config['rates'])
        if any(not isinstance(m, str) or not m.strip() for m in budget.rates):
            raise ValueError('Model allowlist required')
        if parts.hostname not in {'localhost', '127.0.0.1', '::1'} and any(
                r[k] <= 0 for r in budget.rates.values() for k in ('input_per_million', 'output_per_million')):
            raise ValueError('Remote rates must be positive')
        self._url = url.rstrip('/') + '/chat/completions'
        self._key_env = config['api_key_env']
        self._cap = cap
        self._budget = budget
        self._lock = threading.RLock()
        self._events = []
        self._closed = None

    def complete(self, model, messages):
        """One request; no retry, redirects, environment proxy or child overrides."""
        with self._lock:
            if self._closed:
                raise ProviderFailure('AdapterClosed')
            event = {'status': 'denied'}
            try:
                if (not isinstance(model, str) or model not in self._budget.rates or
                        not isinstance(messages, list) or not 1 <= len(messages) <= 128 or any(
                            not isinstance(m, dict) or set(m) != {'role', 'content'} or
                            not isinstance(m['role'], str) or m['role'] not in {'system', 'user', 'assistant'} or
                            not isinstance(m['content'], str) for m in messages)):
                    raise ProviderFailure('InvalidRequest')
                messages = deepcopy(messages)
                encoded = json.dumps(messages, ensure_ascii=False).encode()
                if len(encoded) > 131072:
                    raise ProviderFailure('RequestTooLarge')
                key = os.environ.get(self._key_env, '')
                if not key or any(ord(c) < 33 or ord(c) > 126 for c in key):
                    raise ProviderFailure('CredentialUnavailable')
                # Lazy optional dependency: replay-only installations need no httpx.
                import httpx
                reserved = self._budget.reserve(model, messages, self._cap)
                event.update(model=model, prompt_sha256=hashlib.sha256(encoded).hexdigest(),
                             estimated_cost_reserved_usd=reserved)
                with httpx.Client(trust_env=False, follow_redirects=False,
                                  transport=httpx.HTTPTransport(retries=0, trust_env=False)) as client:
                    with client.stream('POST', self._url,
                                       headers={'Authorization': 'Bearer ' + key, 'Accept-Encoding': 'identity'},
                                       json={'model': model, 'messages': messages,
                                             'max_completion_tokens': self._cap, 'stream': False, 'store': False},
                                       timeout=self._budget.remaining(cap=30)) as response:
                        if response.status_code != 200:
                            raise ProviderFailure('ProviderHTTPError')
                        if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                            raise ProviderFailure('UnsupportedResponseEncoding')
                        chunks, size = [], 0
                        for chunk in response.iter_bytes(chunk_size=4096):
                            self._budget.remaining()
                            size += len(chunk)
                            if size > 131072:
                                raise ProviderFailure('ResponseTooLarge')
                            chunks.append(chunk)
                        data = json.loads(b''.join(chunks))
                self._budget.remaining()
                choices = data.get('choices')
                if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
                    raise ProviderFailure('IncompleteResponse')
                message = choices[0].get('message', {})
                text = message.get('content')
                if (message.get('role') != 'assistant' or not isinstance(text, str) or not text or
                        message.get('tool_calls') or message.get('refusal') or len(text.encode()) > 65536):
                    raise ProviderFailure('InvalidResponse')
                usage = data.get('usage')
                if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                        for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
                    raise ProviderFailure('UsageUnavailable')
                if usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
                    raise ProviderFailure('InvalidUsage')
                rates = self._budget.rates[model]
                cost = (usage['prompt_tokens'] * rates['input_per_million'] +
                        usage['completion_tokens'] * rates['output_per_million']) / 1_000_000
                # Never refund a reservation. Higher reported estimates reduce future headroom.
                self._budget.cost_reserved += max(0, cost - reserved)
                event.update(provider_reported_usage={k: usage[k] for k in
                             ('prompt_tokens', 'completion_tokens', 'total_tokens')},
                             provider_reported_cost_estimate_usd=cost)
                if usage['completion_tokens'] > self._cap or self._budget.cost_reserved > self._budget.limits['max_cost_usd'] + 1e-12:
                    raise ProviderFailure('UsageExceededReservation')
                event.update(status='completed', response_sha256=hashlib.sha256(text.encode()).hexdigest())
                return text
            except Exception as exc:
                code = str(exc) if isinstance(exc, ProviderFailure) else (
                    'BudgetExceeded' if isinstance(exc, BudgetExceeded) else 'ProviderTransportOrResponseError')
                self._closed = code
                event['error_classification'] = code
                raise ProviderFailure(code) from None
            finally:
                if len(self._events) < 64:
                    self._events.append(event)

    def summary(self):
        with self._lock:
            return {'mode': 'host-provider-adapter', 'reserved_calls': self._budget.calls,
                    'output_tokens_reserved': self._budget.output_reserved,
                    'estimated_cost_committed_usd': self._budget.cost_reserved,
                    'stop_reason': self._closed or self._budget.stop_reason,
                    'events': deepcopy(self._events), 'billing_cost_usd': None,
                    'scope': 'Transport observations; provider usage is reported, not independently measured'}
