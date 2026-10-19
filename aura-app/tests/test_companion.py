"""Verify the existing Claude boundary without spending API credit or using real memory."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from memory.sqlite_store import AuraMemoryStore
from companion.memory_extractor import MemoryExtractor
from companion.reaction_engine import CompanionReactionEngine
from brain.llm_provider import ClaudeProvider

class CompanionTest(unittest.TestCase):
    def test_original_personality_memory_and_cloud_provider(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'AURA_BRAIN_PROVIDER':'claude','ANTHROPIC_API_KEY':'test-key','ANTHROPIC_MODEL':'claude-sonnet-4-6'}):
            store=AuraMemoryStore(Path(folder)/'test.db');store.apply_schema()
            user=store.get_or_create_user('Sujan M J','Sujan')
            store.remember_fact(user,'preferred_name','Sujan')
            MemoryExtractor(store).process_user_message(user,'I am nervous about my presentation')
            engine=CompanionReactionEngine(store,use_llm=True)
            with patch.object(ClaudeProvider,'generate',return_value='We can take this one step at a time.') as generate:
                result=engine.generate_reaction(user)
            self.assertIn('LLM provider generated response',result['reasons'])
            self.assertIn('You are AURA',generate.call_args.args[0])
            self.assertIn('presentation',generate.call_args.args[0])
            self.assertTrue(store.get_memory_facts(user))
            store.close()
    def test_sonnet_request_is_server_side(self):
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'test-key','ANTHROPIC_MODEL':'claude-sonnet-4-6'}):
            with patch('urllib.request.urlopen') as request:
                request.return_value.__enter__.return_value.read.return_value=b'{"content":[{"type":"text","text":"Hello Sujan"}]}'
                self.assertEqual(ClaudeProvider().generate('Hello'),'Hello Sujan')
                payload=json.loads(request.call_args.args[0].data)
                self.assertEqual(payload['model'],'claude-sonnet-4-6')
                self.assertIn('AURA',payload['system'])
if __name__=='__main__':unittest.main()
