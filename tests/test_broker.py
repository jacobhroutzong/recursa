import json
import unittest

from recursa.broker import OfflineBroker


def limits(calls=2):
    return {'max_calls': calls, 'max_output_tokens': 4096, 'max_input_bytes': 10000,
            'max_wall_seconds': 60, 'max_cost_usd': 0, 'max_depth': 1, 'max_concurrency': 1, 'max_repairs': 0}


def frame(key=1, **extra):
    return json.dumps({'type': 'completion', 'id': key, 'model': 'm',
                       'messages': [{'role': 'user', 'content': 'Fixture request'}], **extra}).encode()


class OfflineBrokerTests(unittest.TestCase):
    def test_host_budget_denies_before_second_dispatch(self):
        broker = OfflineBroker({'m': 'fixture reply'}, limits(1))
        self.assertTrue(broker.respond(frame())['ok'])
        response = broker.respond(frame(2))
        self.assertFalse(response['ok'])
        self.assertEqual(response['error'], 'BudgetExceeded')
        self.assertEqual(broker.summary()['scripted_dispatches'], 1)
        self.assertEqual(broker.summary()['reserved_calls'], 1)

    def test_urls_headers_overrides_and_unknown_models_are_rejected(self):
        for fields in ({'url': 'https://invalid.example'}, {'headers': {'Authorization': 'private-placeholder'}},
                       {'max_tokens': 1000000}, {'model': 'unconfigured'}, {'messages': [{'role': 'user', 'content': [{'image_url': 'https://invalid.example'}]}]}):
            broker = OfflineBroker({'m': 'reply'}, limits())
            result = broker.respond(frame(**fields))
            self.assertFalse(result['ok'])
            self.assertEqual(broker.summary()['reserved_calls'], 0)
            self.assertNotIn('private-placeholder', json.dumps(broker.summary()))

    def test_replayed_request_does_not_reserve_again(self):
        broker = OfflineBroker({'m': 'reply'}, limits())
        self.assertTrue(broker.respond(frame())['ok'])
        self.assertFalse(broker.respond(frame())['ok'])
        self.assertEqual(broker.summary()['scripted_dispatches'], 1)

    def test_large_response_keeps_reservation_and_is_not_returned(self):
        broker = OfflineBroker({'m': 'x' * 2000}, limits(), max_reply_bytes=1000)
        result = broker.respond(frame())
        self.assertFalse(result['ok'])
        self.assertNotIn('text', result)
        self.assertEqual(broker.summary()['reserved_calls'], 1)
        self.assertEqual(broker.summary()['events'][0]['status'], 'denied')

    def test_wire_expansion_is_bounded_and_errors_are_sanitized(self):
        broker = OfflineBroker({'m': '\x00' * 30000}, limits())
        result = broker.respond(frame())
        self.assertFalse(result['ok'])
        self.assertLess(len(json.dumps(result)), 200)
        malformed = OfflineBroker({'m': 'reply'}, limits())
        self.assertFalse(malformed.respond(b'not json')['ok'])
        self.assertEqual(malformed.summary()['scripted_dispatches'], 0)

    def test_oversized_frames_and_boolean_ids_cannot_spend_budget(self):
        for raw in (b'x' * 131073, frame(True)):
            broker = OfflineBroker({'m': 'reply'}, limits())
            self.assertFalse(broker.respond(raw)['ok'])
            self.assertFalse(broker.respond(frame())['ok'], 'A protocol rejection closes the broker')
            self.assertEqual(broker.summary()['reserved_calls'], 0)
