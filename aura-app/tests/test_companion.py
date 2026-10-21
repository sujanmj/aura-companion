"""Verify the existing Claude boundary without spending API credit or using real memory."""
import json
import os
from contextlib import redirect_stdout
import io
import sqlite3
from pathlib import Path
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from http.server import HTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from memory.sqlite_store import AuraMemoryStore
from companion.memory_extractor import MemoryExtractor
from companion.reaction_engine import CompanionReactionEngine
from brain.prompt_builder import PromptBuilder
from brain.llm_provider import ClaudeProvider, OpenAIProvider
from api.sensor_api_server import AuraSensorAPIHandler, get_sensor_api_token, is_request_authorized
from scripts import pi_node_simulator
from devices.event_bus import DeviceEventBus

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

    def test_visual_memory_is_labeled_uncertain_and_time_scoped_in_prompts(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            owner = store.get_or_create_user('Owner')
            store.add_conversation(owner, 'user', 'Where did I see my keys?')
            store.add_ambient_scene_observation(
                owner, ['living room', 'sofa'], True, 0.42
            )
            prompt = PromptBuilder(store).build_companion_prompt(
                owner, {'situation': 'The user is looking for keys.'}
            )
            self.assertIn('may be inaccurate or stale', prompt)
            self.assertIn('not proof of identity, activity, or exact object location', prompt)
            self.assertIn('confidence=0.42', prompt)
            self.assertIn('recorded=', prompt)
            store.close()

    def test_conversation_history_clear_is_scoped_and_preserves_companion_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            owner = store.get_or_create_user('Owner')
            other = store.get_or_create_user('Other')
            store.add_conversation(owner, 'user', 'private owner message')
            store.add_conversation(other, 'user', 'private other message')
            store.remember_fact(owner, 'favorite_drink', 'tea')
            store.remember_routine(owner, 'fitness_interest', 'swimming')
            store.add_observation(owner, 'ambient_context', 'private camera note')

            self.assertEqual(store.clear_conversation_history(owner), 1)
            self.assertEqual(store.get_recent_conversations(owner), [])
            self.assertEqual(
                store.get_recent_conversations(other)[0]['message'],
                'private other message',
            )
            self.assertEqual(store.get_memory_facts(owner)[0]['fact_value'], 'tea')
            self.assertEqual(store.get_routine_memory(owner)[0]['routine_value'], 'swimming')
            self.assertEqual(
                store.get_latest_observations(owner)[0]['event_summary'],
                'private camera note',
            )
            store.close()

    def test_sensor_node_api_fails_closed_without_a_strong_token(self):
        handler = type('FakeHandler', (), {'headers': {}})()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(get_sensor_api_token())
            self.assertFalse(is_request_authorized(handler))
        with patch.dict(os.environ, {'AURA_SENSOR_API_TOKEN': 'short'}, clear=True):
            self.assertIsNone(get_sensor_api_token())
            self.assertFalse(is_request_authorized(handler))
        token = 'x' * 32
        with patch.dict(os.environ, {'AURA_SENSOR_API_TOKEN': token}, clear=True):
            self.assertEqual(get_sensor_api_token(), token)
            self.assertFalse(is_request_authorized(handler))
            handler.headers = {'X-AURA-API-Token': token + 'wrong'}
            self.assertFalse(is_request_authorized(handler))
            handler.headers = {'X-AURA-API-Token': token}
            self.assertTrue(is_request_authorized(handler))

    def test_sensor_node_http_routes_reject_unauthenticated_events(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'sensor.db')
            store.apply_schema()
            store.conn.close()
            store.conn = sqlite3.connect(Path(folder) / 'sensor.db', check_same_thread=False)
            store.conn.row_factory = sqlite3.Row
            store.conn.execute('PRAGMA foreign_keys=ON;')
            server = HTTPServer(('127.0.0.1', 0), AuraSensorAPIHandler)
            server.aura_store = store
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch('api.sensor_api_server.beat_sensor_api_heartbeat'),
                    patch('api.sensor_api_server.sync_sensor_event'),
                ):
                    with urllib.request.urlopen(base + '/health', timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.loads(response.read())['version'], '0.4')

                    for request in (
                        urllib.request.Request(base + '/events/latest'),
                        urllib.request.Request(
                            base + '/events',
                            data=json.dumps({
                                'event_type': 'test',
                                'event_summary': 'must not be stored',
                            }).encode(),
                            headers={'Content-Type': 'application/json'},
                            method='POST',
                        ),
                    ):
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(request, timeout=2)
                        self.assertEqual(error.exception.code, 401)
                        error.exception.close()

                    token = 't' * 32
                    with patch.dict(os.environ, {'AURA_SENSOR_API_TOKEN': token}, clear=True):
                        request = urllib.request.Request(base + '/events/latest', headers={'X-AURA-API-Token': token})
                        with urllib.request.urlopen(request, timeout=2) as response:
                            self.assertEqual(response.status, 200)

                        request = urllib.request.Request(
                            base + '/events',
                            data=json.dumps({
                                'event_type': 'bad_id',
                                'event_summary': 'invalid ID should be rejected',
                                'event_uuid': 7,
                            }).encode(),
                            headers={
                                'Content-Type': 'application/json',
                                'X-AURA-API-Token': token,
                            },
                            method='POST',
                        )
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(request, timeout=2)
                        self.assertEqual(error.exception.code, 400)
                        error.exception.close()

                        request = urllib.request.Request(
                            base + '/nodes/enroll',
                            data=json.dumps({
                                'node_id': 'pi_bedroom_node',
                                'display_name': 'Bedroom Pi',
                                'room': 'bedroom',
                            }).encode(),
                            headers={
                                'Content-Type': 'application/json',
                                'X-AURA-API-Token': token,
                            },
                            method='POST',
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:
                            enrollment = json.loads(response.read())
                        node_token = enrollment['token']
                        self.assertNotIn(
                            node_token,
                            store.conn.execute('SELECT token_hash FROM sensor_nodes').fetchone()[0],
                        )

                        request = urllib.request.Request(
                            base + '/nodes/heartbeat',
                            data=json.dumps({'node_id': 'pi_bedroom_node'}).encode(),
                            headers={'Content-Type': 'application/json', 'X-AURA-API-Token': node_token},
                            method='POST',
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:
                            self.assertTrue(json.loads(response.read())['ok'])

                        request = urllib.request.Request(
                            base + '/nodes/status',
                            headers={'X-AURA-API-Token': token},
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:
                            nodes = json.loads(response.read())['nodes']
                        self.assertEqual(nodes[0]['node_id'], 'pi_bedroom_node')
                        self.assertTrue(nodes[0]['online'])

                        node_event = {
                            'event_type': 'node_check',
                            'event_summary': 'node-authenticated event',
                            'source': 'spoofed_source',
                            'room': 'spoofed_room',
                            'severity': 'low',
                            'confidence': 0.5,
                            'requires_action': False,
                            'event_uuid': '3b6cfd8c-5874-4213-bbe0-b8e814d4721f',
                        }
                        missing_id = {key: value for key, value in node_event.items() if key != 'event_uuid'}
                        request = urllib.request.Request(
                            base + '/events',
                            data=json.dumps(missing_id).encode(),
                            headers={
                                'Content-Type': 'application/json',
                                'X-AURA-API-Token': node_token,
                            },
                            method='POST',
                        )
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(request, timeout=2)
                        self.assertEqual(error.exception.code, 400)
                        error.exception.close()

                        request = urllib.request.Request(
                            base + '/events',
                            data=json.dumps(node_event).encode(),
                            headers={
                                'Content-Type': 'application/json',
                                'X-AURA-API-Token': node_token,
                            },
                            method='POST',
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:
                            node_event_response = json.loads(response.read())
                        self.assertEqual(node_event_response['event']['source'], 'pi_bedroom_node')
                        self.assertEqual(node_event_response['event']['room'], 'bedroom')

                        request = urllib.request.Request(
                            base + '/nodes/revoke',
                            data=json.dumps({'node_id': 'pi_bedroom_node'}).encode(),
                            headers={
                                'Content-Type': 'application/json',
                                'X-AURA-API-Token': token,
                            },
                            method='POST',
                        )
                        with urllib.request.urlopen(request, timeout=2) as response:
                            self.assertTrue(json.loads(response.read())['revoked'])
                        request = urllib.request.Request(
                            base + '/nodes/heartbeat',
                            data=json.dumps({'node_id': 'pi_bedroom_node'}).encode(),
                            headers={'Content-Type': 'application/json', 'X-AURA-API-Token': node_token},
                            method='POST',
                        )
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            urllib.request.urlopen(request, timeout=2)
                        self.assertEqual(error.exception.code, 401)
                        error.exception.close()

                        event = {
                            'event_type': 'retry_test',
                            'event_summary': 'one event despite retry',
                            'source': 'test_node',
                            'room': 'lab',
                            'severity': 'low',
                            'confidence': 0.5,
                            'requires_action': False,
                            'event_uuid': '8a5e0f4e-76ea-44fc-969e-7a412d152ca4',
                        }
                        responses = []
                        for _ in range(2):
                            request = urllib.request.Request(
                                base + '/events',
                                data=json.dumps(event).encode(),
                                headers={
                                    'Content-Type': 'application/json',
                                    'X-AURA-API-Token': token,
                                },
                                method='POST',
                            )
                            with urllib.request.urlopen(request, timeout=2) as response:
                                responses.append(json.loads(response.read()))
                        self.assertFalse(responses[0]['event']['duplicate'])
                        self.assertTrue(responses[1]['event']['duplicate'])
                        self.assertEqual(responses[0]['event']['event_id'], responses[1]['event']['event_id'])

                event_count = store.conn.execute('SELECT COUNT(*) FROM device_events').fetchone()[0]
                self.assertEqual(event_count, 2)
                observation_count = store.conn.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
                self.assertEqual(observation_count, 2)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
                store.close()

    def test_device_event_bus_deduplicates_client_event_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'events.db')
            store.apply_schema()
            user = store.get_or_create_user('Owner')
            bus = DeviceEventBus(store)
            first = bus.publish_event(
                user, 'movement', 'Movement detected', source='bedroom_node',
                external_event_id='sensor-event-123',
            )
            duplicate = bus.publish_event(
                user, 'movement', 'Retry must not replace original', source='bedroom_node',
                external_event_id='sensor-event-123',
            )
            self.assertEqual(first['event_id'], duplicate['event_id'])
            self.assertFalse(first['duplicate'])
            self.assertTrue(duplicate['duplicate'])
            self.assertEqual(store.conn.execute('SELECT COUNT(*) FROM device_events').fetchone()[0], 1)
            self.assertEqual(store.conn.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 1)
            store.close()

    def test_schema_migration_adds_event_deduplication_to_existing_databases(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.db'
            connection = sqlite3.connect(path)
            connection.executescript('''
                CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE device_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_summary TEXT NOT NULL,
                    source TEXT DEFAULT 'unknown',
                    room TEXT,
                    severity TEXT DEFAULT 'low',
                    confidence REAL DEFAULT 0.5,
                    requires_action INTEGER DEFAULT 0,
                    action_status TEXT DEFAULT 'none',
                    metadata_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            connection.close()
            store = AuraMemoryStore(path)
            store.apply_schema()
            columns = {row['name'] for row in store.conn.execute('PRAGMA table_info(device_events)')}
            indexes = {row['name'] for row in store.conn.execute('PRAGMA index_list(device_events)')}
            self.assertIn('external_event_id', columns)
            self.assertIn('idx_device_events_external_id', indexes)
            store.close()

    def test_pi_simulator_retries_with_the_same_idempotency_key(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"ok": true}'

        payload = pi_node_simulator.build_payload('bedroom', 'movement_absent')
        with (
            patch.object(pi_node_simulator.urllib.request, 'urlopen', side_effect=[
                urllib.error.URLError('temporary disconnect'), Response()
            ]) as urlopen,
            patch.object(pi_node_simulator.time, 'sleep'),
        ):
            self.assertEqual(pi_node_simulator.post_event('http://127.0.0.1:8787', payload, 't' * 32), {'ok': True})
        self.assertEqual(urlopen.call_count, 2)
        requests = [call.args[0] for call in urlopen.call_args_list]
        self.assertEqual(json.loads(requests[0].data)['event_uuid'], payload['event_uuid'])
        self.assertEqual(json.loads(requests[1].data)['event_uuid'], payload['event_uuid'])

    def test_pi_simulator_never_logs_token_and_requires_configuration(self):
        token = 's' * 32
        output = io.StringIO()
        with (
            patch.object(pi_node_simulator, 'load_env_file'),
            patch.object(pi_node_simulator, 'post_event', return_value={'ok': True}),
            patch.dict(os.environ, {'AURA_SENSOR_API_TOKEN': token}, clear=True),
            redirect_stdout(output),
        ):
            self.assertEqual(
                pi_node_simulator.send_simulated_event('bedroom', 'fall_detected'),
                0,
            )
        self.assertNotIn(token, output.getvalue())
        self.assertNotIn(token[:8], output.getvalue())
        self.assertIn('AURA_PI_NODE_AUTH_CONFIGURED', output.getvalue())

        output = io.StringIO()
        with (
            patch.object(pi_node_simulator, 'load_env_file'),
            patch.object(pi_node_simulator, 'post_event') as post_event,
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(output),
        ):
            self.assertEqual(
                pi_node_simulator.send_simulated_event('bedroom', 'fall_detected'),
                1,
            )
        post_event.assert_not_called()

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

    def test_explicit_emotional_negation_does_not_create_or_reuse_mood_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            user = store.get_or_create_user('Owner')
            MemoryExtractor(store).process_user_message(
                user,
                "I'm not anxious about my interview and I'm not sad; can you recommend a book?",
            )

            facts = store.get_memory_facts(user)
            inference = CompanionReactionEngine(store).infer_situation(
                CompanionReactionEngine(store).build_context(user)
            )

            self.assertNotIn('recent_anxiety', [fact['fact_key'] for fact in facts])
            self.assertNotIn('recent_low_mood', [fact['fact_key'] for fact in facts])
            self.assertFalse(inference['has_anxiety_signal'])
            self.assertFalse(inference['has_low_mood_signal'])
            self.assertEqual(inference['emotional_need'], 'presence')
            store.close()

    def test_uncertain_emotional_language_does_not_become_a_saved_mood_or_reuse_old_mood(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            user = store.get_or_create_user('Owner')
            extractor = MemoryExtractor(store)
            extractor.process_user_message(user, 'I felt anxious about my interview last week.')
            actions = extractor.process_user_message(
                user,
                "I'm not sure whether I'm anxious about tomorrow, and maybe a little sad.",
            )

            inference = CompanionReactionEngine(store).infer_situation(
                CompanionReactionEngine(store).build_context(user)
            )

            self.assertNotIn('remembered fact: recent_anxiety', actions)
            self.assertNotIn('remembered fact: recent_low_mood', actions)
            self.assertFalse(inference['has_anxiety_signal'])
            self.assertFalse(inference['has_low_mood_signal'])
            self.assertEqual(inference['emotional_need'], 'presence')
            store.close()

    def test_clear_current_emotion_overrides_an_earlier_uncertain_mention(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            user = store.get_or_create_user('Owner')
            MemoryExtractor(store).process_user_message(
                user,
                "I'm not sure if I'm anxious, but I am worried about my interview.",
            )
            inference = CompanionReactionEngine(store).infer_situation(
                CompanionReactionEngine(store).build_context(user)
            )
            self.assertTrue(inference['has_anxiety_signal'])
            self.assertEqual(inference['emotional_need'], 'encouragement')
            store.close()

    def test_a_later_positive_emotion_cue_overrides_an_earlier_negated_cue(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AuraMemoryStore(Path(folder) / 'test.db')
            store.apply_schema()
            user = store.get_or_create_user('Owner')
            MemoryExtractor(store).process_user_message(
                user, "I'm not nervous, but I am anxious about my interview."
            )
            inference = CompanionReactionEngine(store).infer_situation(
                CompanionReactionEngine(store).build_context(user)
            )
            self.assertTrue(inference['has_anxiety_signal'])
            self.assertEqual(inference['emotional_need'], 'encouragement')
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
                sent=request.call_args.args[0]
                self.assertEqual(sent.full_url,'https://api.anthropic.com/v1/messages')
                self.assertEqual(sent.method,'POST')
                self.assertEqual(sent.get_header('X-api-key'),'test-key')
                self.assertEqual(sent.get_header('Anthropic-version'),'2023-06-01')
                self.assertNotIn('test-key',sent.full_url)
                payload=json.loads(sent.data)
                self.assertEqual(payload['model'],'claude-sonnet-4-6')
                self.assertIn('AURA',payload['system'])

    def test_claude_failures_redact_provider_body_prompt_and_key(self):
        api_key='private-api-key-sentinel'
        prompt='private-prompt-sentinel'
        body='private-provider-body-sentinel'
        failure=urllib.error.HTTPError(
            'https://api.anthropic.com/v1/messages',
            500,
            'provider error',
            None,
            io.BytesIO(body.encode()),
        )
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':api_key,'ANTHROPIC_MODEL':'test-model'}):
            with patch('urllib.request.urlopen',side_effect=failure):
                output=io.StringIO()
                with redirect_stdout(output):
                    self.assertIsNone(ClaudeProvider().generate(prompt))
        logged=output.getvalue()
        self.assertIn('HTTP 500',logged)
        for private_value in (api_key,prompt,body):
            self.assertNotIn(private_value,logged)

    def test_claude_unexpected_errors_are_redacted(self):
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'test-key','ANTHROPIC_MODEL':'test-model'}):
            with patch('urllib.request.urlopen',side_effect=RuntimeError('private-runtime-sentinel')):
                output=io.StringIO()
                with redirect_stdout(output):
                    self.assertIsNone(ClaudeProvider().generate('private-prompt-sentinel'))
        self.assertIn('request failed or response was invalid',output.getvalue())
        self.assertNotIn('private-runtime-sentinel',output.getvalue())
        self.assertNotIn('private-prompt-sentinel',output.getvalue())

    def test_openai_failures_redact_provider_body_prompt_and_key(self):
        api_key='private-openai-key-sentinel'
        prompt='private-openai-prompt-sentinel'
        body='private-openai-provider-body-sentinel'
        failure=urllib.error.HTTPError(
            'https://api.openai.com/v1/responses',
            500,
            'provider error',
            None,
            io.BytesIO(body.encode()),
        )
        with patch.dict(os.environ,{'OPENAI_API_KEY':api_key,'OPENAI_MODEL':'test-model'}):
            with patch('urllib.request.urlopen',side_effect=failure):
                output=io.StringIO()
                with redirect_stdout(output):
                    self.assertIsNone(OpenAIProvider().generate(prompt))
        logged=output.getvalue()
        self.assertIn('HTTP 500',logged)
        for private_value in (api_key,prompt,body):
            self.assertNotIn(private_value,logged)

    def test_openai_unexpected_errors_are_redacted(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-openai-key','OPENAI_MODEL':'test-model'}):
            with patch('urllib.request.urlopen',side_effect=RuntimeError('private-openai-runtime-sentinel')):
                output=io.StringIO()
                with redirect_stdout(output):
                    self.assertIsNone(OpenAIProvider().generate('private-openai-prompt-sentinel'))
        self.assertIn('request failed or response was invalid',output.getvalue())
        self.assertNotIn('private-openai-runtime-sentinel',output.getvalue())
        self.assertNotIn('private-openai-prompt-sentinel',output.getvalue())
if __name__=='__main__':unittest.main()
