from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from shared_conversation import shared_contribution

class SharedConversationTests(unittest.TestCase):
    def test_consent_and_bounds_precede_provider_access(self):
        with patch('shared_conversation.brain_readiness') as readiness:
            for message, consent in [('hello', False), ('hello', 'true'), ('', True), ('x'*4001, True)]:
                with self.assertRaises(ValueError):
                    shared_contribution(message, consent)
            readiness.assert_not_called()

    def test_reviewed_text_is_the_only_personal_input(self):
        prompts = []
        with patch('shared_conversation.brain_readiness', return_value={'provider':'claude', 'state':'configured_unverified'}):
            result = shared_contribution('What board game could we play?', True,
                generate=lambda prompt: prompts.append(prompt) or 'Try a cooperative game.')
        self.assertEqual(result['provider'], 'claude')
        self.assertFalse(result['saved'])
        self.assertFalse(result['online_verified'])
        self.assertEqual(len(prompts), 1)
        self.assertTrue(prompts[0].endswith('What board game could we play?'))
        self.assertIn('No tools or web lookup are available', prompts[0])

    def test_local_mode_never_calls_a_provider_and_failure_is_honest(self):
        with patch('shared_conversation.brain_readiness', return_value={'provider':'local', 'state':'local_only'}):
            result = shared_contribution('hello', True, generate=lambda _: self.fail('unexpected provider call'))
        self.assertEqual(result['provider'], 'local')
        with patch('shared_conversation.brain_readiness', return_value={'provider':'claude', 'state':'configured_unverified'}):
            def fail(_): raise RuntimeError('private provider error')
            result = shared_contribution('hello', True, generate=fail)
        self.assertNotIn('private provider error', str(result))
        self.assertIn('unavailable', result['response'])

if __name__ == '__main__': unittest.main()
