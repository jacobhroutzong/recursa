import json
import unittest
from unittest.mock import patch

from recursa.provider import ProviderAdapter, ProviderFailure

try:
    import httpx
except ImportError:
    httpx = None


def config():
    return {'base_url': 'https://provider.invalid/v1', 'api_key_env': 'RECURSA_TEST_KEY',
            'output_tokens': 32, 'rates': {'fixture': {'input_per_million': 1, 'output_per_million': 2}},
            'budget': {'max_calls': 2, 'max_output_tokens': 64, 'max_input_bytes': 10000,
                       'max_wall_seconds': 60, 'max_cost_usd': 0.1, 'max_concurrency': 1,
                       'max_depth': 1, 'max_repairs': 0}}


def result(**changes):
    return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'fixture reply'}}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8}, **changes}


MESSAGES = [{'role': 'user', 'content': 'private fixture prompt'}]


class ProviderConfigurationTests(unittest.TestCase):
    def test_authorization_and_fixed_configuration(self):
        for flag in (False, None, 1, 'true'):
            with self.assertRaises(ValueError):
                ProviderAdapter(config(), authorize_live=flag)
        for changes in ({'headers': {}}, {'base_url': 'http://remote.invalid/v1'},
                        {'base_url': 'https://user:secret@provider.invalid/v1'},
                        {'base_url': 'https://provider.invalid/v1?token=x'},
                        {'base_url': 'https://provider.invalid:bad/v1'},
                        {'base_url': 'https://provider.invalid/\n'},
                        {'api_key_env': 'literal key'}, {'output_tokens': True},
                        {'rates': {'fixture': {'input_per_million': 0, 'output_per_million': 0}}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ProviderAdapter({**config(), **changes}, authorize_live=True)


@unittest.skipIf(httpx is None, 'Optional HTTP transport not installed')
class ProviderTransportTests(unittest.TestCase):
    def execute(self, body=None, *, status=200, configuration=None, handler=None):
        self.requests = []
        self.adapter = ProviderAdapter(configuration or config(), authorize_live=True)

        def intercepted(request):
            self.requests.append(request)
            if handler:
                return handler(request)
            return httpx.Response(status, json=body if body is not None else result())

        self.key_patch = patch.dict('os.environ', {'RECURSA_TEST_KEY': 'fake-test-credential'})
        self.transport_patch = patch('httpx.HTTPTransport', return_value=httpx.MockTransport(intercepted))
        self.key_patch.start()
        self.transport_factory = self.transport_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.addCleanup(self.transport_patch.stop)
        return self.adapter

    def test_fixed_request_usage_privacy_and_no_refund(self):
        adapter = self.execute()
        self.assertEqual(adapter.complete('fixture', MESSAGES), 'fixture reply')
        request = self.requests[0]
        self.assertEqual(str(request.url), 'https://provider.invalid/v1/chat/completions')
        self.assertEqual(json.loads(request.content), {'model': 'fixture', 'messages': MESSAGES,
                         'max_completion_tokens': 32, 'stream': False, 'store': False})
        self.assertEqual(request.headers['Authorization'], 'Bearer fake-test-credential')
        summary = adapter.summary()
        self.assertGreater(summary['estimated_cost_committed_usd'], 0.000011)
        self.assertEqual(summary['events'][0]['provider_reported_usage']['total_tokens'], 8)
        for private in ('private fixture prompt', 'fake-test-credential', 'fixture reply', 'provider.invalid'):
            self.assertNotIn(private, json.dumps(summary))
        summary['events'][0]['status'] = 'tampered'
        self.assertEqual(adapter.summary()['events'][0]['status'], 'completed')
        self.assertIsNone(summary['billing_cost_usd'])
        self.transport_factory.assert_called_once_with(retries=0, trust_env=False)
        self.assertEqual(request.extensions['timeout']['read'], request.extensions['timeout']['connect'])

    def test_compressed_response_is_rejected_before_decoding(self):
        adapter = self.execute(handler=lambda request: httpx.Response(
            200, headers={'Content-Encoding': 'gzip'}, stream=httpx.ByteStream(b'not decoded')))
        with self.assertRaisesRegex(ProviderFailure, 'UnsupportedResponseEncoding'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(adapter.summary()['reserved_calls'], 1)

    def test_call_budget_denies_before_transport(self):
        cfg = config()
        cfg['budget']['max_calls'] = 1
        adapter = self.execute(configuration=cfg)
        adapter.complete('fixture', MESSAGES)
        with self.assertRaisesRegex(ProviderFailure, 'BudgetExceeded'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(len(self.requests), 1)

    def test_invalid_input_and_missing_key_never_dispatch(self):
        for model, messages in [('other', MESSAGES), ('fixture', [{'role': [], 'content': 'x'}]),
                                ('fixture', [{'role': 'user', 'content': 'x', 'url': 'bad'}]),
                                ('fixture', [{'role': 'user', 'content': 'x' * 131073}])]:
            adapter = self.execute()
            with self.assertRaises(ProviderFailure):
                adapter.complete(model, messages)
            self.assertEqual(len(self.requests), 0)
            self.assertEqual(adapter.summary()['reserved_calls'], 0)
        adapter = self.execute()
        with patch.dict('os.environ', {'RECURSA_TEST_KEY': ''}), self.assertRaisesRegex(ProviderFailure, 'CredentialUnavailable'):
            adapter.complete('fixture', MESSAGES)
        self.assertEqual(adapter.summary()['reserved_calls'], 0)

    def test_http_errors_and_redirects_are_not_retried(self):
        for status in (302, 429, 500):
            adapter = self.execute({'error': 'private-provider-body'}, status=status)
            with self.assertRaisesRegex(ProviderFailure, '^ProviderHTTPError$'):
                adapter.complete('fixture', MESSAGES)
            with self.assertRaisesRegex(ProviderFailure, '^AdapterClosed$'):
                adapter.complete('fixture', MESSAGES)
            self.assertEqual(len(self.requests), 1)
            self.assertEqual(adapter.summary()['reserved_calls'], 1)
            self.assertNotIn('private-provider-body', json.dumps(adapter.summary()))

    def test_missing_invalid_usage_and_incomplete_results_fail_closed(self):
        for body in (result(usage=None), result(usage={'prompt_tokens': True, 'completion_tokens': 3, 'total_tokens': 4}),
                     result(usage={'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 9}),
                     result(choices=[{'finish_reason': 'length'}]), [],
                     result(choices=[{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'x', 'tool_calls': ['x']}}])):
            adapter = self.execute(body)
            with self.assertRaises(ProviderFailure):
                adapter.complete('fixture', MESSAGES)
            self.assertEqual(adapter.summary()['reserved_calls'], 1)
            self.assertNotEqual(adapter.summary()['events'][0]['status'], 'completed')

    def test_oversized_and_transport_failures_keep_reservation(self):
        def error(request):
            raise httpx.ReadTimeout('private exception and credential', request=request)
        for handler in (error, lambda request: httpx.Response(200, content=b'x' * 131073)):
            adapter = self.execute(handler=handler)
            with self.assertRaises(ProviderFailure) as caught:
                adapter.complete('fixture', MESSAGES)
            self.assertNotIn('private', str(caught.exception))
            self.assertEqual(adapter.summary()['reserved_calls'], 1)
            self.assertEqual(len(self.requests), 1)

    def test_reported_overrun_reduces_headroom_and_closes_adapter(self):
        for usage in ({'prompt_tokens': 5, 'completion_tokens': 33, 'total_tokens': 38},
                      {'prompt_tokens': 200000, 'completion_tokens': 3, 'total_tokens': 200003}):
            adapter = self.execute(result(usage=usage))
            with self.assertRaisesRegex(ProviderFailure, 'UsageExceededReservation'):
                adapter.complete('fixture', MESSAGES)
            self.assertEqual(len(self.requests), 1)
            self.assertGreater(adapter.summary()['estimated_cost_committed_usd'], 0)
