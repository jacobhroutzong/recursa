"""Host-owned completion gate for scripted and supervised provider backends."""
import hashlib
import json
import threading

from recursa.budget import BudgetExceeded, CallBudget
from recursa.provider import ProviderFailure

PREFIX = b'RECURSA_RPC_V1 '
FRAME_LIMIT = 131072


class _CompletionBroker:
    def __init__(self, models, max_reply_bytes):
        self.models = frozenset(models)
        self.max_reply_bytes = max_reply_bytes
        self.events, self.next_id = [], 1
        self.closed_reason = None
        self.lock = threading.RLock()

    def respond(self, raw, *, deadline=None):
        with self.lock:
            key = None
            event = {'status': 'denied'}
            try:
                if self.closed_reason:
                    raise ValueError('BrokerClosed')
                if not isinstance(raw, bytes) or len(raw) > FRAME_LIMIT:
                    raise ValueError('FrameTooLarge')
                request = json.loads(raw)
                if not isinstance(request, dict) or set(request) != {'type', 'id', 'model', 'messages'}:
                    raise ValueError('InvalidRequestFields')
                if request['type'] != 'completion' or type(request['id']) is not int or request['id'] != self.next_id:
                    raise ValueError('InvalidRequestSequence')
                key = request['id']
                model, messages = request['model'], request['messages']
                if not isinstance(model, str) or model not in self.models:
                    raise ValueError('UnconfiguredModel')
                if not isinstance(messages, list) or not 1 <= len(messages) <= 128 or any(
                    not isinstance(m, dict) or set(m) != {'role', 'content'} or
                    m['role'] not in {'system', 'user', 'assistant'} or not isinstance(m['content'], str) for m in messages):
                    raise ValueError('TextMessagesRequired')
                self.next_id += 1
                event.update(id=key, model=model, prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest())
                if deadline is not None:
                    deadline.remaining()
                text = self._dispatch(model, messages, event, deadline)
                if len(text.encode()) > self.max_reply_bytes:
                    raise ValueError('ResponseTooLarge')
                response = {'type': 'completion-result', 'id': key, 'ok': True, 'text': text}
                if len(json.dumps(response).encode()) > FRAME_LIMIT:
                    raise ValueError('ResponseFrameTooLarge')
                event.update(status='completed', response_sha256=hashlib.sha256(text.encode()).hexdigest())
                return response
            except (BudgetExceeded, ProviderFailure, ValueError, TypeError, KeyError, RecursionError) as error:
                if isinstance(error, BudgetExceeded) or (isinstance(error, ProviderFailure) and str(error) == 'BudgetExceeded'):
                    code = 'BudgetExceeded'
                elif isinstance(error, ProviderFailure):
                    code = 'ProviderFailure'
                else:
                    code = 'ProtocolError'
                self.closed_reason = code
                event['error_classification'] = code
                return {'type': 'completion-result', 'id': key, 'ok': False, 'error': code}
            except KeyboardInterrupt:
                self.closed_reason = 'Cancelled'
                event['error_classification'] = 'Cancelled'
                raise
            finally:
                if len(self.events) < 64:
                    self.events.append(event)


class OfflineBroker(_CompletionBroker):
    """Never accepts provider URLs, headers, credentials or executable callbacks.

    Container requests are untrusted. This class can return only configured
    strings, and cannot invoke a network provider. Host counters are authoritative.
    """
    def __init__(self, replies, limits, *, output_tokens=2048, max_reply_bytes=65536):
        if not isinstance(replies, dict) or not replies or any(not isinstance(k, str) or not k or not isinstance(v, str) for k, v in replies.items()):
            raise ValueError('Scripted replies must map model names to text')
        if type(output_tokens) is not int or output_tokens <= 0 or type(max_reply_bytes) is not int or not 1 <= max_reply_bytes <= 65536:
            raise ValueError('Output reservations and byte limits must be bounded')
        self.replies = dict(replies)
        self.output_tokens = output_tokens
        self.budget = CallBudget(limits, {name: {'input_per_million': 0, 'output_per_million': 0} for name in replies})
        self.dispatches = 0
        super().__init__(replies, max_reply_bytes)

    def _dispatch(self, model, messages, event, deadline):
        event['estimated_cost_reserved_usd'] = self.budget.reserve(model, messages, self.output_tokens)
        self.dispatches += 1
        self.budget.remaining()
        return self.replies[model]

    def summary(self):
        return {'mode': 'offline-scripted-broker', 'live_inference': False,
                'reserved_calls': self.budget.calls, 'scripted_dispatches': self.dispatches,
                'output_tokens_reserved': self.budget.output_reserved,
                'estimated_cost_reserved_usd': self.budget.cost_reserved,
                'stop_reason': self.closed_reason or self.budget.stop_reason,
                'events': list(self.events),
                'scope': 'Host-observed scripted requests; no real provider or measured inference tokens'}


class ProviderBroker(_CompletionBroker):
    """Host-only bridge with fixed provider settings and one shared call budget."""

    def __init__(self, config, private_output_dir, *, authorize_live=False):
        from recursa.provider_worker import SupervisedProviderAdapter
        self._adapter = SupervisedProviderAdapter(config, private_output_dir, authorize_live=authorize_live)
        super().__init__(self._adapter.models, 65536)

    def _dispatch(self, model, messages, event, deadline):
        return self._adapter.complete(model, messages, deadline=deadline)

    def summary(self):
        return {'mode': 'supervised-provider-broker', 'live_inference': None,
                'stop_reason': self.closed_reason, 'events': list(self.events),
                'provider': self._adapter.summary(),
                'scope': 'Host transport observations with provider-reported usage and estimated cost'}
