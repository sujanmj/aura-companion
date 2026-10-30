from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from grounded_answer import answer_from_sources


SOURCES = [{
    'id': 42,
    'title': 'Example topic',
    'url': 'https://en.wikipedia.org/?curid=42',
    'excerpt': 'A bounded source excerpt.',
}]


class GroundedAnswerTests(unittest.TestCase):
    def test_requires_exact_consent_and_bounds_before_provider_access(self):
        with patch('grounded_answer.brain_readiness') as readiness:
            for question, sources, consent in [
                ('hello', SOURCES, False), ('hello', SOURCES, 'true'),
                ('', SOURCES, True), ('x' * 1001, SOURCES, True),
                ('hello', [], True),
            ]:
                with self.subTest(question_length=len(question) if isinstance(question, str) else None):
                    with self.assertRaises(ValueError):
                        answer_from_sources(question, sources, consent)
            readiness.assert_not_called()

    def test_prompt_contains_only_reviewed_question_and_bounded_sources(self):
        prompts = []
        with patch('grounded_answer.brain_readiness', return_value={
            'provider': 'claude', 'state': 'configured_unverified',
        }):
            result = answer_from_sources(
                'What is this?', SOURCES, True,
                generate=lambda prompt: prompts.append(prompt) or 'It is an example [1].',
            )
        self.assertEqual(result['provider'], 'claude')
        self.assertFalse(result['saved'])
        self.assertFalse(result['online_verified'])
        self.assertIn('Example topic', prompts[0])
        self.assertIn('[1] Example topic', prompts[0])
        self.assertTrue(prompts[0].endswith('What is this?'))
        self.assertIn('untrusted data', prompts[0])
        self.assertIn('no saved memory or tools', prompts[0])

    def test_invalid_citations_urls_and_oversized_excerpts_are_rejected(self):
        invalid = [
            [{**SOURCES[0], 'url': 'https://evil.test/source'}],
            [{**SOURCES[0], 'id': True}],
            [{**SOURCES[0], 'excerpt': 'x' * 1601}],
            [SOURCES[0], SOURCES[0]],
            [SOURCES[0]] * 4,
        ]
        with patch('grounded_answer.brain_readiness') as readiness:
            for sources in invalid:
                with self.subTest(sources=len(sources)):
                    with self.assertRaises(ValueError):
                        answer_from_sources('question', sources, True)
            readiness.assert_not_called()

    def test_local_only_and_provider_failure_are_reported_without_inventing_answer(self):
        with patch('grounded_answer.brain_readiness', return_value={
            'provider': 'local', 'state': 'local_only',
        }):
            result = answer_from_sources('question', SOURCES, True,
                generate=lambda _: self.fail('local-only must not call a provider'))
        self.assertEqual(result['provider'], 'local')
        self.assertIn('no language model is configured', result['response'])
        with patch('grounded_answer.brain_readiness', return_value={
            'provider': 'openai', 'state': 'configured_unverified',
        }):
            result = answer_from_sources('question', SOURCES, True,
                generate=lambda _: (_ for _ in ()).throw(RuntimeError('private provider detail')))
        self.assertIn('unavailable', result['response'])
        self.assertNotIn('private provider detail', result['response'])


if __name__ == '__main__':
    unittest.main()
