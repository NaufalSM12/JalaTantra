"""Unit tests for the optional read-only AI advisor."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import ai


class AITests(unittest.TestCase):
    def setUp(self):
        self.config = {'ai_config': '/nonexistent/ai.json', 'allowed_networks': ['127.0.0.0/8']}

    def test_unconfigured_by_default(self):
        with patch.object(ai.db, 'settings', return_value=self.config):
            self.assertIsNone(ai.settings())
            self.assertEqual(ai.status(), {'available': False})
            with self.assertRaises(ai.AIUnavailable):
                ai.summarise_incident(1)

    def test_disabled_or_incomplete_config_is_ignored(self):
        for data in ({'enabled': False, 'api_key': 'k', 'model': 'm', 'base_url': 'https://x'},
                     {'enabled': True, 'api_key': ' ', 'model': 'm', 'base_url': 'https://x'},
                     {'enabled': True, 'api_key': 'k', 'model': '', 'base_url': 'https://x'},
                     {'enabled': True, 'api_key': 'k', 'model': 'm', 'base_url': 'ftp://x'},
                     'not-a-dict'):
            with patch.object(ai.db, 'settings', return_value={'ai_config': str(None)}), \
                 patch.object(Path, 'read_text', return_value=json.dumps(data) if isinstance(data, dict) else data):
                self.assertIsNone(ai.settings())

    def test_valid_config_is_accepted_and_normalized(self):
        data = {'enabled': True, 'api_key': 'secret-key', 'model': 'test-model',
                'base_url': 'https://provider.example/v1/'}
        with patch.object(ai, 'settings', return_value={'api_key': 'secret-key', 'model': 'test-model',
                                                        'base_url': 'https://provider.example/v1',
                                                        'timeout': 20, 'max_tokens': 600}):
            self.assertEqual(ai.status(), {'available': True, 'model': 'test-model'})

    def test_request_is_readonly_post_with_bearer_and_never_logs_key(self):
        config = {'api_key': 'secret-key', 'model': 'm', 'base_url': 'https://x/v1', 'timeout': 5, 'max_tokens': 10}
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({'choices': [{'message': {'content': 'Ringkasan.'}}]}).encode()
        with patch.object(ai, '_open', return_value=response) as opener:
            result = ai._request(config, {'messages': []})
        self.assertEqual(result, 'Ringkasan.')
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertTrue(request.full_url.startswith('https://x/v1/chat/completions'))
        self.assertEqual(request.get_header('Authorization'), 'Bearer secret-key')

    def test_provider_errors_raise_unavailable_without_leaking_details(self):
        config = {'api_key': 'k', 'model': 'm', 'base_url': 'https://x', 'timeout': 1, 'max_tokens': 10}
        with patch.object(ai, '_open', side_effect=ai.urllib.error.URLError('http://x password=secret')):
            with self.assertRaises(ai.AIUnavailable) as raised:
                ai._request(config, {'messages': []})
        self.assertNotIn('secret', str(raised.exception))
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'not json'
        with patch.object(ai, '_open', return_value=response):
            with self.assertRaises(ai.AIUnavailable):
                ai._request(config, {'messages': []})

    def test_provider_http_errors_explain_cause_without_leaking_key(self):
        config = {'api_key': 'secret-key', 'model': 'm', 'base_url': 'https://x', 'timeout': 1, 'max_tokens': 10}

        def failing(code, body):
            error = ai.urllib.error.HTTPError('https://x', code, 'err', {}, None)
            error.read = lambda *a: json.dumps(body).encode()
            return error

        cases = ((401, {'error': {'message': 'No auth credentials found'}}, 'ditolak'),
                 (404, {'error': {'message': 'This model is unavailable for free. use z-ai/glm-5.2'}}, 'tidak ditemukan'),
                 (429, {'error': {'message': 'rate limited'}}, 'Kuota'),
                 (503, {'error': {}}, 'bermasalah'))
        for code, body, needle in cases:
            with patch.object(ai, '_open', side_effect=failing(code, body)):
                with self.assertRaises(ai.AIUnavailable) as raised:
                    ai._request(config, {'messages': []})
                message = str(raised.exception)
                self.assertIn(needle, message, (code, message))
                self.assertNotIn('secret-key', message)

    def test_redirect_is_rejected_before_the_key_can_be_forwarded(self):
        config = {'api_key': 'secret-key', 'model': 'm', 'base_url': 'https://x', 'timeout': 1, 'max_tokens': 10}
        error = ai.urllib.error.HTTPError('https://x', 302, 'redirect', {}, None)
        error.read = lambda *args: b''
        with patch.object(ai, '_open', side_effect=error):
            with self.assertRaises(ai.AIUnavailable) as raised:
                ai._request(config, {'messages': []})
        self.assertIn('diblokir', str(raised.exception))
        self.assertNotIn('secret-key', str(raised.exception))

    def test_missing_host_gives_actionable_message(self):
        config = {'api_key': 'k', 'model': 'm', 'base_url': 'https://api.openrouter.ai/v1', 'timeout': 1, 'max_tokens': 10}
        error = ai.urllib.error.URLError(OSError(-2, 'Name or service not known'))
        with patch.object(ai, '_open', side_effect=error):
            with self.assertRaises(ai.AIUnavailable) as raised:
                ai._request(config, {'messages': []})
        self.assertIn('host', str(raised.exception).lower())

    def test_prompt_contains_only_visible_facts(self):
        context = {'incident': {'device_name': 'db01', 'device_address': '127.0.0.1', 'device_kind': 'server',
                                'device_site': 'Lab', 'device_environment': 'real', 'device_status': 'down',
                                'title': 'SSH tidak merespons', 'severity': 'critical', 'status': 'open',
                                'assignee': None, 'details': 'layanan mati', 'resolution_note': None},
                   'checks': [{'status': 'down', 'results_json': '[{"service":"ssh","status":"down","detail":"tidak merespons"}]', 'created_at': 'T'}],
                   'audit': [{'actor': 'admin', 'action': 'job.succeeded', 'detail': 'restart #1', 'created_at': 'T'}],
                   'jobs': [{'action': 'restart_service', 'service': 'ssh', 'status': 'succeeded', 'created_at': 'T'}]}
        prompt = ai.build_prompt(context)
        for needle in ('db01', 'SSH tidak merespons', 'restart_service', 'job.succeeded'):
            self.assertIn(needle, prompt)
        self.assertNotIn('password', prompt.lower())

    def test_summarise_requires_existing_incident(self):
        with patch.object(ai, 'settings', return_value={'api_key': 'k', 'model': 'm', 'base_url': 'https://x',
                                                        'timeout': 5, 'max_tokens': 10}), \
             patch.object(ai.db, 'one', return_value=None):
            with self.assertRaises(ai.AIUnavailable):
                ai.summarise_incident(99)

    def test_summarise_returns_read_only_marker(self):
        config = {'api_key': 'k', 'model': 'm', 'base_url': 'https://x', 'timeout': 5, 'max_tokens': 10}
        context = {'incident': {'device_name': 'db01', 'device_address': '127.0.0.1', 'device_kind': 'server',
                                'device_site': '', 'device_environment': 'real', 'device_status': 'down',
                                'title': 'T', 'severity': 'critical', 'status': 'open', 'assignee': None,
                                'details': '', 'resolution_note': None},
                   'checks': [], 'audit': [], 'jobs': []}
        with patch.object(ai, 'settings', return_value=config), \
             patch.object(ai, 'incident_context', return_value=context), \
             patch.object(ai, '_request', return_value='Ringkasan kondisi.'):
            result = ai.summarise_incident(1)
        self.assertTrue(result['read_only'])
        self.assertEqual(result['summary'], 'Ringkasan kondisi.')


if __name__ == '__main__':
    unittest.main()
