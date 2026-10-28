"""Explicit room invitation leases; no capture, inference, speech or memory recall."""
from contextlib import contextmanager
import time
import uuid


class HandoffDenied(ValueError):
    pass


class RoomHandoff:
    LEASE_SECONDS = 300
    MAX_CLAIMS = 1000

    def __init__(self, store):
        self.store = store
        self.db = store.conn

    @contextmanager
    def _transaction(self):
        # Serializes claim checks and writes across independent hub connections.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('DELETE FROM room_sessions WHERE expires_at <= ?', (time.time(),))
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _online(self, user_id, node_id):
        if not isinstance(node_id, str):
            raise HandoffDenied('invalid_node')
        node = self.db.execute(
            """SELECT node_id FROM sensor_nodes WHERE user_id=? AND node_id=?
               AND disabled=0 AND last_seen_at >= datetime('now', '-90 seconds')""",
            (user_id, node_id),
        ).fetchone()
        if not node:
            raise HandoffDenied('node_unavailable')

    def _session(self, user_id, session_id, generation):
        if not isinstance(session_id, str) or type(generation) is not int:
            raise HandoffDenied('invalid_session')
        row = self.db.execute('SELECT * FROM room_sessions WHERE user_id=?', (user_id,)).fetchone()
        if not row or row['session_id'] != session_id or row['generation'] != generation:
            raise HandoffDenied('stale_session')
        return dict(row)

    def status(self, user_id):
        with self._transaction():
            row = self.db.execute('SELECT * FROM room_sessions WHERE user_id=?', (user_id,)).fetchone()
            return dict(row) if row else None

    def start(self, user_id, node_id, approved):
        if approved is not True:
            raise HandoffDenied('approval_required')
        with self._transaction():
            self._online(user_id, node_id)
            if self.db.execute('SELECT 1 FROM room_sessions WHERE user_id=?', (user_id,)).fetchone():
                raise HandoffDenied('session_already_active')
            session_id = str(uuid.uuid4())
            self.db.execute('INSERT INTO room_sessions VALUES (?, ?, ?, 1, ?)',
                            (user_id, session_id, node_id, time.time() + self.LEASE_SECONDS))
            return self._session(user_id, session_id, 1)

    def transfer(self, user_id, session_id, generation, node_id, approved):
        if approved is not True:
            raise HandoffDenied('approval_required')
        with self._transaction():
            self._session(user_id, session_id, generation)
            self._online(user_id, node_id)
            # Transfer does not renew consent; the original five-minute deadline remains.
            self.db.execute('UPDATE room_sessions SET node_id=?, generation=generation+1 WHERE user_id=?',
                            (node_id, user_id))
            return self._session(user_id, session_id, generation + 1)

    def stop(self, user_id, session_id, generation):
        with self._transaction():
            self._session(user_id, session_id, generation)
            self.db.execute('DELETE FROM room_sessions WHERE user_id=?', (user_id,))

    def claim(self, token, session_id, generation, turn_id):
        try:
            if not isinstance(turn_id, str) or str(uuid.UUID(turn_id)) != turn_id:
                raise ValueError()
        except (ValueError, AttributeError):
            raise HandoffDenied('invalid_turn') from None
        with self._transaction():
            node = self.store.get_sensor_node_by_token(token)
            if not node:
                raise HandoffDenied('node_unauthorized')
            user_id = node['user_id']
            session = self._session(user_id, session_id, generation)
            if session['node_id'] != node['node_id']:
                raise HandoffDenied('node_not_invited')
            self._online(user_id, node['node_id'])
            if self.db.execute('SELECT 1 FROM room_reply_claims WHERE session_id=? AND turn_id=?',
                               (session_id, turn_id)).fetchone():
                raise HandoffDenied('turn_already_claimed')
            count = self.db.execute('SELECT count(*) FROM room_reply_claims WHERE session_id=?',
                                    (session_id,)).fetchone()[0]
            if count >= self.MAX_CLAIMS:
                raise HandoffDenied('session_capacity_reached')
            self.db.execute('INSERT INTO room_reply_claims VALUES (?, ?, ?, ?, ?)',
                            (user_id, session_id, turn_id, node['node_id'], generation))
            return {'reserved': True, 'session_id': session_id, 'turn_id': turn_id,
                    'generation': generation, 'expires_at': session['expires_at']}
