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
from cloud.supabase_sync import sync_conversation


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
                if op == 'status':
                    result = {'provider': os.environ.get('AURA_BRAIN_PROVIDER', 'local'),
                              'model': os.environ.get('ANTHROPIC_MODEL', ''),
                              'facts': store.get_memory_facts(user),
                              'conversations': list(reversed(store.get_recent_conversations(user, limit=30))),
                              'observations': list(reversed(store.get_latest_observations(user, limit=10)))}
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
