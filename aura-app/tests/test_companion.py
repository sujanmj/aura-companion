"""Verify the existing Claude boundary without spending API credit or using real memory."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from memory.sqlite_store import AuraMemoryStore
from companion.memory_extractor import MemoryExtractor
from companion.reaction_engine import CompanionReactionEngine
from brain.llm_provider import ClaudeProvider

class CompanionTest(unittest.TestCase):
    def test_checkins_default_off_and_honor_idle_interval_and_quiet_hours(self):
        with tempfile.TemporaryDirectory() as folder:
            store=AuraMemoryStore(Path(folder)/'test.db');store.apply_schema()
            user=store.get_or_create_user('Owner','Alex')
            store.add_conversation(user,'user','Checking in')
            store.conn.execute(
                "UPDATE conversation_logs SET created_at=? WHERE user_id=? AND role='user'",
                ('2026-01-01 10:00:00', user),
            )
            store.conn.commit()
            now=datetime(2026,1,2,21,30,tzinfo=timezone.utc)
            self.assertIsNone(store.create_checkin_if_due(user,now))
            store.update_companion_preferences(user,True,'22:00','08:00',4)
            first=store.create_checkin_if_due(user,now)
            self.assertTrue(first['check_in'])
            self.assertIn('Alex, just checking in',first['response'])
            self.assertIsNone(store.create_checkin_if_due(user,now.replace(hour=22,minute=30)))
            self.assertIsNone(store.create_checkin_if_due(user,datetime(2026,1,3,1,0,tzinfo=timezone.utc)))
            next_day=store.create_checkin_if_due(user,datetime(2026,1,3,10,0,tzinfo=timezone.utc))
            self.assertTrue(next_day['check_in'])
            self.assertIsNone(store.create_checkin_if_due(user,datetime(2026,1,3,10,1,tzinfo=timezone.utc)))
            store.close()

    def test_checkin_preferences_reject_invalid_times_and_intervals(self):
        with tempfile.TemporaryDirectory() as folder:
            store=AuraMemoryStore(Path(folder)/'test.db');store.apply_schema()
            user=store.get_or_create_user('Owner')
            for start, end, interval in [('25:00','08:00',24),('22:00','8 am',24),('22:00','08:00',3)]:
                with self.assertRaises(ValueError):
                    store.update_companion_preferences(user,True,start,end,interval)
            self.assertFalse(store.get_companion_preferences(user)['checkins_enabled'])
            store.close()

    def test_memory_export_is_scoped_to_the_selected_user(self):
        with tempfile.TemporaryDirectory() as folder:
            store=AuraMemoryStore(Path(folder)/'test.db');store.apply_schema()
            owner=store.get_or_create_user('Owner')
            other=store.get_or_create_user('Other')
            store.add_conversation(owner,'user','private owner message')
            store.add_conversation(other,'user','other user message')
            store.remember_fact(owner,'favorite_drink','tea')
            store.remember_fact(other,'favorite_drink','coffee')
            exported=store.export_user_memory(owner)
            self.assertEqual(exported['format'],'aura-memory-export')
            self.assertEqual(exported['user']['name'],'Owner')
            self.assertEqual(exported['records']['conversation_logs'][0]['message'],'private owner message')
            self.assertEqual(exported['records']['memory_facts'][0]['fact_value'],'tea')
            self.assertNotIn('other user message',str(exported))
            self.assertNotIn('coffee',str(exported))
            store.close()

    def test_routines_can_be_corrected_forgotten_and_explicitly_remembered_again(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            owner = store.get_or_create_user('Owner')
            other = store.get_or_create_user('Other')
            store.remember_routine(owner, 'fitness_interest', 'Likes gym.', source='user')
            routine = store.get_routine_memory(owner)[0]
            self.assertTrue(store.update_memory_routine(owner, routine['id'], 'Prefers swimming.'))
            self.assertEqual(store.get_routine_memory(owner)[0]['routine_value'], 'Prefers swimming.')
            self.assertFalse(store.update_memory_routine(other, routine['id'], 'Other user data'))
            self.assertFalse(store.delete_memory_routine(other, routine['id']))
            self.assertTrue(store.delete_memory_routine(owner, routine['id']))
            self.assertEqual(store.get_routine_memory(owner), [])

            store.remember_routine(owner, 'fitness_interest', 'Detected gym interest.', source='conversation')
            self.assertEqual(store.get_routine_memory(owner), [])
            store.remember_routine(owner, 'fitness_interest', 'User confirmed gym interest.', source='user_correction')
            self.assertEqual(store.get_routine_memory(owner)[0]['routine_value'], 'User confirmed gym interest.')
            with self.assertRaises(ValueError):
                store.update_memory_routine(owner, routine['id'], '  ')
            store.close()

    def test_observations_can_only_be_deleted_by_their_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            owner = store.get_or_create_user('Owner')
            other = store.get_or_create_user('Other')
            observation_id = store.add_observation(
                owner, 'ambient_context', 'Local camera context', source='mac_local'
            )
            self.assertFalse(store.delete_observation(other, observation_id))
            self.assertTrue(store.delete_observation(owner, observation_id))
            self.assertEqual(store.get_latest_observations(owner), [])
            store.close()

    def test_old_emotion_and_quiet_camera_context_do_not_label_current_mood(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            user = store.get_or_create_user('Owner')
            store.add_conversation(user, 'user', 'I am anxious about my interview')
            store.add_conversation(user, 'assistant', 'I am here with you.')
            store.add_conversation(user, 'user', 'Can you recommend a good book?')
            store.add_observation(
                user, 'ambient_context', 'A person is sitting quietly.', source='mac_local'
            )

            inference = CompanionReactionEngine(store).infer_situation(
                CompanionReactionEngine(store).build_context(user)
            )

            self.assertFalse(inference['has_anxiety_signal'])
            self.assertFalse(inference['has_presentation_signal'])
            self.assertFalse(inference['has_low_mood_signal'])
            self.assertEqual(inference['emotional_need'], 'presence')
            store.close()
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
