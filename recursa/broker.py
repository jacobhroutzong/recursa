"""Host-owned completion gate. Only a scripted backend is implemented."""
import hashlib
import json
import threading

from recursa.budget import BudgetExceeded, CallBudget

PREFIX = b'RECURSA_RPC_V1 '
FRAME_LIMIT = 131072


class OfflineBroker:
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
        self.output_tokens, self.max_reply_bytes = output_tokens, max_reply_bytes
        self.budget = CallBudget(limits, {name: {'input_per_million': 0, 'output_per_million': 0} for name in replies})
        self.events, self.next_id, self.dispatches = [], 1, 0
        self.closed_reason = None
        self.lock = threading.RLock()

    def respond(self, raw):
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
                key = request['id']
                if request['type'] != 'completion' or type(key) is not int or key != self.next_id:
                    raise ValueError('InvalidRequestSequence')
                model, messages = request['model'], request['messages']
                if not isinstance(model, str) or model not in self.replies:
                    raise ValueError('UnconfiguredModel')
                if not isinstance(messages, list) or not 1 <= len(messages) <= 128 or any(
                    not isinstance(m, dict) or set(m) != {'role', 'content'} or
                    m['role'] not in {'system', 'user', 'assistant'} or not isinstance(m['content'], str) for m in messages):
                    raise ValueError('TextMessagesRequired')
                self.next_id += 1
                event.update(id=key, model=model, prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest())
                reservation = self.budget.reserve(model, messages, self.output_tokens)
                event['estimated_cost_reserved_usd'] = reservation
                self.dispatches += 1
                text = self.replies[model]
                if len(text.encode()) > self.max_reply_bytes:
                    raise ValueError('ResponseTooLarge')
                self.budget.remaining()
                response = {'type': 'completion-result', 'id': key, 'ok': True, 'text': text}
                if len(json.dumps(response).encode()) > FRAME_LIMIT:
                    raise ValueError('ResponseFrameTooLarge')
                event.update(status='completed', response_sha256=hashlib.sha256(text.encode()).hexdigest())
                return response
            except BudgetExceeded:
                self.closed_reason = 'BudgetExceeded'
                event['error_classification'] = 'BudgetExceeded'
                return {'type': 'completion-result', 'id': key, 'ok': False, 'error': 'BudgetExceeded'}
            except (ValueError, TypeError, KeyError):
                self.closed_reason = 'ProtocolError'
                event['error_classification'] = 'ProtocolError'
                return {'type': 'completion-result', 'id': key, 'ok': False, 'error': 'ProtocolError'}
            finally:
                if len(self.events) < 64:
                    self.events.append(event)

    def summary(self):
        return {'mode': 'offline-scripted-broker', 'live_inference': False,
                'reserved_calls': self.budget.calls, 'scripted_dispatches': self.dispatches,
                'output_tokens_reserved': self.budget.output_reserved,
                'estimated_cost_reserved_usd': self.budget.cost_reserved,
                'stop_reason': self.closed_reason or self.budget.stop_reason,
                'events': list(self.events),
                'scope': 'Host-observed scripted requests; no real provider or measured inference tokens'}
