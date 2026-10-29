"""Loopback-only Ollama transport checks; no installed model or external service."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from brain.llm_provider import LLMProvider, OllamaProvider


class OllamaTransportTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.behavior = "normal"
        parent = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_POST(self):
                parent.requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                if parent.behavior == 'redirect':
                    self.send_response(302)
                    self.send_header('Location', 'http://example.com/api/generate')
                    self.end_headers()
                    return
                if parent.behavior == 'large':
                    body = b'x' * (OllamaProvider.MAX_RESPONSE_BYTES + 1)
                elif parent.behavior == 'invalid':
                    body = b'not json'
                elif parent.behavior == 'huge-reply':
                    body = json.dumps({'response': 'x' * (OllamaProvider.MAX_REPLY_CHARS + 1)}).encode()
                else:
                    body = json.dumps({'response': 'नमस्ते — AURA'}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_loopback_uses_selected_model_and_round_trips_unicode(self):
        with patch.dict('os.environ', {
            'OLLAMA_MODEL': 'local-model',
            'OLLAMA_URL': self.base + '/api/generate',
        }):
            provider = LLMProvider(provider_name='ollama')
        self.assertIsInstance(provider.provider, OllamaProvider)
        self.assertEqual(provider.provider.model_name, 'local-model')
        self.assertEqual(provider.provider.generate('नमस्ते'), 'नमस्ते — AURA')
        path, body = self.requests[-1]
        self.assertEqual(path, '/api/generate')
        self.assertEqual(body, {'model': 'local-model', 'prompt': 'नमस्ते', 'stream': False})

    def test_non_loopback_urls_and_unbounded_prompts_are_never_sent(self):
        for url in (
            'https://127.0.0.1/api/generate',
            'http://example.com/api/generate',
            'http://127.0.0.1.evil.test/api/generate',
            self.base + '/other',
            self.base + '/api/generate?next=http://example.com',
            'http://user:pass@127.0.0.1/api/generate',
        ):
            self.assertIsNone(OllamaProvider(ollama_url=url).generate('private prompt'))
        self.assertIsNone(OllamaProvider(ollama_url=self.base + '/api/generate').generate('x' * 20001))
        self.assertIsNone(OllamaProvider(ollama_url=self.base + '/api/generate').generate('  '))
        self.assertEqual(self.requests, [])

    def test_redirects_are_not_followed_and_bad_or_oversized_replies_fail_closed(self):
        for mode in ('redirect', 'large', 'invalid', 'huge-reply'):
            self.behavior = mode
            self.assertIsNone(OllamaProvider(ollama_url=self.base + '/api/generate').generate('hello'))
        self.assertEqual([p for p, _ in self.requests], ['/api/generate'] * 4)

    def test_greeting_detection_uses_words_not_substrings(self):
        sys.path.insert(0, str(ROOT))
        from companion.context_relevance import ContextRelevanceFilter
        relevance = ContextRelevanceFilter()
        for greeting in ('hi', 'hello aura', 'how are you?', 'good morning aura'):
            self.assertTrue(relevance.is_generic_greeting(greeting), greeting)
        for ordinary_message in (
            'this matters to me',
            'I have been thinking about the day',
            'which option seems safer?',
        ):
            self.assertFalse(relevance.is_generic_greeting(ordinary_message), ordinary_message)

    def test_readiness_reports_the_selected_ollama_model_without_probing(self):
        path = ROOT / 'aura-app' / 'server' / 'readiness.py'
        spec = importlib.util.spec_from_file_location('aura_readiness_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.brain_readiness({'AURA_BRAIN_PROVIDER': 'ollama', 'OLLAMA_MODEL': 'selected'})
        self.assertEqual(result['model'], 'selected')
        self.assertEqual(result['state'], 'configured_unverified')


if __name__ == '__main__':
    unittest.main()
