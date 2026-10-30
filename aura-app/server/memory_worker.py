"""Private newline-JSON service: existing AURA owns all memory and personality."""
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from config.env_loader import load_env_file
from memory.sqlite_store import AuraMemoryStore, DEFAULT_DB_PATH
from companion.memory_extractor import MemoryExtractor
from companion.reaction_engine import CompanionReactionEngine
from cloud.supabase_sync import (
    discard_pending_conversations,
    enqueue_conversation_deletions,
    start_retry_worker,
    sync_conversation,
)
from readiness import brain_readiness, test_provider_connection
from shared_conversation import shared_contribution
from companion.private_session import generate_private_response


def main():
    load_env_file()
    path = Path(os.environ.get('AURA_DB_PATH', str(DEFAULT_DB_PATH))).expanduser().resolve()
    # SQLite backup API includes committed WAL contents; never reset/import over memory.
    if path.exists():
        backup_dir = path.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        with sqlite3.connect(path) as source, sqlite3.connect(backup_dir / f'aura-{stamp}.db') as dest:
            source.backup(dest)
    store = AuraMemoryStore(path)
    store.apply_schema()
    start_retry_worker()
    user = store.get_or_create_user('Sujan M J', 'Sujan')
    if os.environ.get('AURA_USER_ID'):
        user = int(os.environ['AURA_USER_ID'])
        if not store.conn.execute('SELECT id FROM users WHERE id=?', (user,)).fetchone():
            raise ValueError('AURA_USER_ID does not exist')
    engine = CompanionReactionEngine(store, use_llm=True)
    extractor = MemoryExtractor(store)
    for line in sys.stdin:
        req = {}
        try:
            req = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                op = req['op']
                if op != 'private_chat':
                    store.expire_observations(user)
                if op == 'private_chat':
                    result = generate_private_response(req.get('message'))
                elif op == 'readiness':
                    store.conn.execute('SELECT 1').fetchone()
                    result = {'brain': brain_readiness(), 'memory': 'available'}
                elif op == 'provider_test':
                    result = test_provider_connection()
                elif op == 'status':
                    brain = brain_readiness()
                    result = {'provider': brain['provider'],
                              'model': brain['model'],
                              'facts': store.get_memory_facts(user),
                              'conversations': list(reversed(store.get_recent_conversations(user, limit=30))),
                              'observations': list(reversed(store.get_latest_observations(user, limit=20))),
                              'routines': store.get_routine_memory(user),
                              'reminders': store.get_routine_reminders(user),
                              'people': [
                                  {key: person.get(key) for key in (
                                      'id', 'display_name', 'relation', 'trust_level',
                                      'consent_to_remember', 'face_profile_status',
                                      'last_seen_at',
                                  )}
                                  for person in store.get_known_people(user)
                              ],
                              'observation_retention': store.observation_retention(user),
                              'preferences': store.get_companion_preferences(user)}
                elif op == 'preferences':
                    result = store.get_companion_preferences(user)
                elif op == 'update_preferences':
                    result = store.update_companion_preferences(
                        user,
                        req.get('checkins_enabled'),
                        req.get('quiet_start'),
                        req.get('quiet_end'),
                        req.get('checkin_interval_hours'),
                    )
                elif op == 'checkin':
                    result = store.create_due_routine_reminder(user)
                    if result is None:
                        result = store.create_checkin_if_due(user)
                    if result is None:
                        result = {'due': False}
                    else:
                        result['due'] = True
                elif op == 'create_reminder':
                    reminder_id = store.add_routine_reminder(
                        user,
                        req.get('label'),
                        req.get('local_time'),
                        req.get('days_of_week'),
                    )
                    result = {'created': True, 'reminder_id': reminder_id}
                elif op == 'update_reminder':
                    reminder_id = req.get('reminder_id')
                    if not isinstance(reminder_id, int) or isinstance(reminder_id, bool) or reminder_id <= 0:
                        raise ValueError('Invalid reminder')
                    if not store.update_routine_reminder(
                        user,
                        reminder_id,
                        req.get('label'),
                        req.get('local_time'),
                        req.get('days_of_week'),
                    ):
                        raise ValueError('Reminder not found')
                    result = {'ok': True}
                elif op == 'delete_reminder':
                    reminder_id = req.get('reminder_id')
                    if not isinstance(reminder_id, int) or isinstance(reminder_id, bool) or reminder_id <= 0:
                        raise ValueError('Invalid reminder')
                    if not store.delete_routine_reminder(user, reminder_id):
                        raise ValueError('Reminder not found')
                    result = {'ok': True}
                elif op == 'set_reminder_enabled':
                    reminder_id = req.get('reminder_id')
                    enabled = req.get('enabled')
                    if not isinstance(reminder_id, int) or isinstance(reminder_id, bool) or reminder_id <= 0:
                        raise ValueError('Invalid reminder')
                    result = store.set_routine_reminder_enabled(user, reminder_id, enabled)
                    result = {'ok': result is None, 'reason': result}
                elif op == 'dismiss_reminder':
                    reminder_id = req.get('reminder_id')
                    if not isinstance(reminder_id, int) or isinstance(reminder_id, bool) or reminder_id <= 0:
                        raise ValueError('Invalid reminder')
                    if not store.dismiss_routine_reminder(user, reminder_id):
                        raise ValueError('Reminder not found')
                    result = {'ok': True}
                elif op == 'acknowledge_reminder':
                    reminder_id = req.get('reminder_id')
                    if not isinstance(reminder_id, int) or isinstance(reminder_id, bool) or reminder_id <= 0:
                        raise ValueError('Invalid reminder')
                    if not store.acknowledge_routine_reminder(user, reminder_id):
                        raise ValueError('Reminder not found or no delivered reminder to acknowledge')
                    result = {'ok': True}
                elif op == 'export':
                    result = store.export_user_memory(user)
                elif op == 'clear_conversations':
                    pending_ids = [
                        int(row['id'])
                        for row in store.conn.execute(
                            'SELECT id FROM conversation_logs WHERE user_id=?', (user,)
                        ).fetchall()
                    ]
                    deleted = store.clear_conversation_history(user)
                    discard_pending_conversations(pending_ids)
                    enqueue_conversation_deletions(pending_ids)
                    result = {'deleted': deleted}
                elif op == 'preview_observation_expiry':
                    result = store.preview_observation_expiry(user, req.get('days'))
                elif op == 'set_observation_retention':
                    result = store.set_observation_retention(user, req.get('days'))
                elif op == 'clear_observations':
                    result = {'deleted': store.clear_observations(user)}
                elif op == 'update_fact':
                    fact_id = req.get('fact_id')
                    value = req.get('value')
                    if not isinstance(fact_id, int) or isinstance(fact_id, bool) or fact_id <= 0:
                        raise ValueError('Invalid memory fact')
                    if not isinstance(value, str):
                        raise ValueError('Invalid memory fact')
                    if not store.update_memory_fact(user, fact_id, value):
                        raise ValueError('Memory fact not found')
                    result = {'ok': True}
                elif op == 'delete_fact':
                    fact_id = req.get('fact_id')
                    if not isinstance(fact_id, int) or isinstance(fact_id, bool) or fact_id <= 0:
                        raise ValueError('Invalid memory fact')
                    if not store.delete_memory_fact(user, fact_id):
                        raise ValueError('Memory fact not found')
                    result = {'ok': True}
                elif op == 'update_routine':
                    routine_id = req.get('routine_id')
                    value = req.get('value')
                    if not isinstance(routine_id, int) or isinstance(routine_id, bool) or routine_id <= 0:
                        raise ValueError('Invalid memory routine')
                    if not isinstance(value, str):
                        raise ValueError('Invalid memory routine')
                    if not store.update_memory_routine(user, routine_id, value):
                        raise ValueError('Memory routine not found')
                    result = {'ok': True}
                elif op == 'delete_routine':
                    routine_id = req.get('routine_id')
                    if not isinstance(routine_id, int) or isinstance(routine_id, bool) or routine_id <= 0:
                        raise ValueError('Invalid memory routine')
                    if not store.delete_memory_routine(user, routine_id):
                        raise ValueError('Memory routine not found')
                    result = {'ok': True}
                elif op == 'delete_observation':
                    observation_id = req.get('observation_id')
                    if not isinstance(observation_id, int) or isinstance(observation_id, bool) or observation_id <= 0:
                        raise ValueError('Invalid observation')
                    if not store.delete_observation(user, observation_id):
                        raise ValueError('Observation not found')
                    result = {'ok': True}
                elif op == 'correct_observation':
                    observation_id = req.get('observation_id')
                    value = req.get('value')
                    if not isinstance(observation_id, int) or isinstance(observation_id, bool) or observation_id <= 0:
                        raise ValueError('Invalid observation')
                    if not isinstance(value, str):
                        raise ValueError('Invalid observation correction')
                    if not store.correct_observation(user, observation_id, value):
                        raise ValueError('Observation not found')
                    result = {'ok': True}
                elif op == 'create_person':
                    name = req.get('display_name')
                    relation = req.get('relation') or None
                    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                        raise ValueError('Invalid person name')
                    if relation is not None and (
                        not isinstance(relation, str) or len(relation.strip()) > 100
                    ):
                        raise ValueError('Invalid person relation')
                    if req.get('consent_to_remember') is not True:
                        raise ValueError('Consent is required')
                    name = name.strip()
                    if store.find_known_person(user, name):
                        result = {'created': False, 'reason': 'already_exists'}
                    else:
                        person_id = store.add_known_person(
                            user,
                            name,
                            relation=relation.strip() if relation else None,
                            trust_level='known',
                            consent_to_remember=True,
                        )
                        store.add_person_event(
                            user,
                            person_id,
                            'person_introduced',
                            f'{name} was introduced to AURA.',
                            source='manual',
                        )
                        result = {
                            'created': True,
                            'person_id': person_id,
                            'display_name': name,
                        }
                elif op == 'forget_person':
                    person_id = req.get('person_id')
                    if not isinstance(person_id, int) or isinstance(person_id, bool) or person_id <= 0:
                        raise ValueError('Invalid person')
                    if not store.forget_known_person(user, person_id):
                        raise ValueError('Person not found')
                    result = {'ok': True}
                elif op == 'ambient_scene':
                    result = store.add_ambient_scene_observation(
                        user,
                        req.get('labels'),
                        req.get('human_present'),
                        req.get('confidence'),
                    )
                elif op == 'shared_chat':
                    result = shared_contribution(req.get('message'), req.get('consent'), req.get('history'))
                elif op == 'chat':
                    message = req['message']
                    if not isinstance(message, str) or not 0 < len(message.strip()) <= 8000:
                        raise ValueError('Invalid message')
                    observation = req.get('observation', '')
                    if isinstance(observation, str) and observation.strip():
                        store.add_observation(user, event_type='ambient_context', event_summary=observation[:500], confidence=0.75, source='mac_local')
                    actions = extractor.process_user_message(user, message.strip())
                    result = engine.generate_reaction(user)
                    result['id'] = store.add_conversation(user, role='assistant', message=result['response'], emotion_tag=result['tone'])
                    rows = store.conn.execute(
                        "SELECT id, role, message, created_at FROM conversation_logs "
                        "WHERE user_id=? ORDER BY id DESC LIMIT 2", (user,)
                    ).fetchall()
                    for row in reversed(rows):
                        threading.Thread(
                            target=sync_conversation,
                            args=(row['id'], row['role'], row['message'], row['created_at']),
                            name='aura-cloud-chat-sync',
                            daemon=True,
                        ).start()
                    result['memory_actions'] = actions
                    result['provider'] = os.environ.get('AURA_BRAIN_PROVIDER', 'local') if 'LLM provider generated response' in result['reasons'] else 'local'
                elif op == 'feedback':
                    if req['rating'] not in ('good', 'bad', 'neutral'):
                        raise ValueError('Invalid rating')
                    row = store.conn.execute("SELECT message, emotion_tag FROM conversation_logs WHERE id=? AND user_id=? AND role='assistant'", (req['response_id'], user)).fetchone()
                    if not row:
                        raise ValueError('Response not found')
                    store.add_response_feedback(user, response_text=row['message'], rating=req['rating'], feedback_text=str(req.get('note', ''))[:2000], tone=row['emotion_tag'])
                    result = {'ok': True}
                else:
                    raise ValueError('Unknown operation')
            print(json.dumps({'id': req['id'], 'result': result}), flush=True)
        except Exception:
            print(json.dumps({'id': req.get('id'), 'error': 'Memory request failed. Check configuration and database access.'}), flush=True)
    store.close()

if __name__ == '__main__':
    main()
