"""Readiness must never confuse configuration with a successful provider call."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('readiness', Path(__file__).resolve().parents[1] / 'server/readiness.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReadinessTests(unittest.TestCase):
    def test_default_is_rule_based_local(self):
        self.assertEqual(module.brain_readiness({})['state'], 'local_only')

    def test_missing_claude_configuration_is_actionable(self):
        value = module.brain_readiness({'AURA_BRAIN_PROVIDER': 'claude'})
        self.assertEqual(value['state'], 'missing_configuration')
        self.assertEqual(value['missing'], ['ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL'])

    def test_configured_does_not_mean_verified_and_keys_are_never_returned(self):
        value = module.brain_readiness({'AURA_BRAIN_PROVIDER': 'CLAUDE', 'ANTHROPIC_API_KEY': 'private-key-sentinel', 'ANTHROPIC_MODEL': 'my-model'})
        self.assertEqual(value['state'], 'configured_unverified')
        self.assertNotIn('private-key-sentinel', json.dumps(value))
        self.assertEqual(value['provider'], 'claude')

    def test_model_matches_the_selected_provider(self):
        value = module.brain_readiness({'AURA_BRAIN_PROVIDER': 'openai', 'OPENAI_API_KEY': 'private-key', 'OPENAI_MODEL': 'selected-model', 'ANTHROPIC_MODEL': 'wrong-provider-model'})
        self.assertEqual(value['model'], 'selected-model')
        self.assertEqual(value['state'], 'configured_unverified')

    def test_stub_and_unknown_providers_are_not_reported_ready(self):
        for provider in ['gemini', 'groq', 'unknown']:
            self.assertEqual(module.brain_readiness({'AURA_BRAIN_PROVIDER': provider})['state'], 'unavailable')

    def test_ollama_needs_a_live_check_too(self):
        self.assertEqual(module.brain_readiness({'AURA_BRAIN_PROVIDER': 'ollama'})['state'], 'configured_unverified')

    def test_provider_test_skips_network_without_a_configured_provider(self):
        called = []
        value = module.test_provider_connection({'AURA_BRAIN_PROVIDER': 'local'}, lambda prompt: called.append(prompt))
        self.assertEqual(value, {'provider': 'local', 'state': 'local_only', 'verified': False})
        self.assertEqual(called, [])

    def test_provider_test_sends_only_fixed_non_personal_prompt_and_discards_reply(self):
        prompts = []
        env = {'AURA_BRAIN_PROVIDER': 'claude', 'ANTHROPIC_API_KEY': 'private-key', 'ANTHROPIC_MODEL': 'test-model'}
        value = module.test_provider_connection(env, lambda prompt: prompts.append(prompt) or 'AURA connection confirmed.')
        self.assertEqual(prompts, ['Reply with exactly: AURA connection confirmed.'])
        self.assertEqual(value, {'provider': 'claude', 'state': 'live_verified', 'verified': True})
        self.assertNotIn('AURA connection confirmed.', json.dumps(value))

    def test_provider_test_failure_is_sanitized(self):
        env = {'AURA_BRAIN_PROVIDER': 'openai', 'OPENAI_API_KEY': 'private-key'}
        value = module.test_provider_connection(env, lambda _prompt: None)
        self.assertEqual(value, {'provider': 'openai', 'state': 'test_failed', 'verified': False})


if __name__ == '__main__':
    unittest.main()
