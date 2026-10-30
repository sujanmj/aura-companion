"""Room handoff software protocol, using only temporary databases and loopback."""
from pathlib import Path
import concurrent.futures
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import uuid
from http.server import HTTPServer
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memory.sqlite_store import AuraMemoryStore
from devices.room_handoff import RoomHandoff, HandoffDenied
from api.sensor_api_server import AuraSensorAPIHandler
from scripts import pi_node_simulator
from scripts import room_invitation


class RoomHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        self.store = AuraMemoryStore(self.path)
        self.store.apply_schema()
        self.user = self.store.get_or_create_user('Sujan M J', 'Sujan')
        self.other = self.store.get_or_create_user('Other')
        self.tokens = {}
        for name in ('bedroom', 'kitchen'):
            _, self.tokens[name] = self.store.enroll_sensor_node(self.user, name, name, name)
            self.store.touch_sensor_node(self.user, name)
        _, self.tokens['other'] = self.store.enroll_sensor_node(self.other, 'other', 'Other', 'Other')
        self.store.touch_sensor_node(self.other, 'other')
        self.hub = RoomHandoff(self.store)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def start(self):
        return self.hub.start(self.user, 'bedroom', True)

    def test_explicit_approval_and_online_destination(self):
        for consent in (None, False, 'true', 1):
            with self.assertRaisesRegex(HandoffDenied, 'approval_required'):
                self.hub.start(self.user, 'bedroom', consent)
        with self.assertRaisesRegex(HandoffDenied, 'node_unavailable'):
            self.hub.start(self.user, 'other', True)
        self.store.conn.execute("UPDATE sensor_nodes SET last_seen_at=datetime('now','-91 seconds') WHERE node_id='bedroom'")
        self.store.conn.commit()
        with self.assertRaisesRegex(HandoffDenied, 'node_unavailable'):
            self.start()

    def test_transfer_fences_old_node_and_deduplicates_across_rooms(self):
        session = self.start()
        sid = session['session_id']
        turn = str(uuid.uuid4())
        self.assertTrue(self.hub.claim(self.tokens['bedroom'], sid, 1, turn)['reserved'])
        for consent in (False, 'true', 1):
            with self.assertRaisesRegex(HandoffDenied, 'approval_required'):
                self.hub.transfer(self.user, sid, 1, 'kitchen', consent)
        moved = self.hub.transfer(self.user, sid, 1, 'kitchen', True)
        self.assertEqual(moved['expires_at'], session['expires_at'])
        with self.assertRaisesRegex(HandoffDenied, 'stale_session'):
            self.hub.claim(self.tokens['bedroom'], sid, 1, str(uuid.uuid4()))
        with self.assertRaisesRegex(HandoffDenied, 'node_not_invited'):
            self.hub.claim(self.tokens['bedroom'], sid, 2, str(uuid.uuid4()))
        with self.assertRaisesRegex(HandoffDenied, 'turn_already_claimed'):
            self.hub.claim(self.tokens['kitchen'], sid, 2, turn)
        self.assertTrue(self.hub.claim(self.tokens['kitchen'], sid, 2, str(uuid.uuid4()))['reserved'])
        with self.assertRaises(HandoffDenied):
            self.hub.stop(self.user, sid, 1)
        self.hub.stop(self.user, sid, 2)
        self.assertIsNone(self.hub.status(self.user))
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM room_reply_claims').fetchone()[0], 0)

    def test_scope_expiry_and_restart(self):
        session = self.start()
        sid = session['session_id']
        with self.assertRaises(HandoffDenied):
            self.hub.start(self.user, 'kitchen', True)
        with self.assertRaises(HandoffDenied):
            self.hub.claim(self.tokens['other'], sid, 1, str(uuid.uuid4()))
        turn = str(uuid.uuid4())
        self.hub.claim(self.tokens['bedroom'], sid, 1, turn)
        second = AuraMemoryStore(self.path)
        try:
            with self.assertRaisesRegex(HandoffDenied, 'turn_already_claimed'):
                RoomHandoff(second).claim(self.tokens['bedroom'], sid, 1, turn)
        finally:
            second.close()
        self.assertEqual(len(self.store.export_user_memory(self.user)['records']['room_reply_claims']), 1)
        self.assertEqual(self.store.export_user_memory(self.other)['records']['room_reply_claims'], [])
        self.store.conn.execute('UPDATE room_sessions SET expires_at=0')
        self.store.conn.commit()
        with self.assertRaisesRegex(HandoffDenied, 'stale_session'):
            self.hub.claim(self.tokens['bedroom'], sid, 1, str(uuid.uuid4()))
        self.assertIsNone(self.hub.status(self.user))
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM room_reply_claims').fetchone()[0], 0)

    def test_claim_validation_fails_after_transfer_and_stop(self):
        session = self.start()
        sid = session['session_id']
        turn = str(uuid.uuid4())
        claim = self.hub.claim(self.tokens['bedroom'], sid, 1, turn)
        self.assertEqual(
            self.hub.validate_claim(self.tokens['bedroom'], sid, 1, turn), claim
        )

        moved = self.hub.transfer(self.user, sid, 1, 'kitchen', True)
        with self.assertRaisesRegex(HandoffDenied, 'stale_session'):
            self.hub.validate_claim(self.tokens['bedroom'], sid, 1, turn)
        with self.assertRaisesRegex(HandoffDenied, 'claim_not_found'):
            self.hub.validate_claim(self.tokens['kitchen'], sid, moved['generation'], turn)

        new_turn = str(uuid.uuid4())
        self.hub.claim(self.tokens['kitchen'], sid, moved['generation'], new_turn)
        self.assertTrue(self.hub.validate_claim(
            self.tokens['kitchen'], sid, moved['generation'], new_turn
        )['reserved'])
        self.hub.stop(self.user, sid, moved['generation'])
        with self.assertRaisesRegex(HandoffDenied, 'stale_session'):
            self.hub.validate_claim(self.tokens['kitchen'], sid, moved['generation'], new_turn)

        expired = self.hub.start(self.user, 'bedroom', True)
        expired_turn = str(uuid.uuid4())
        self.hub.claim(self.tokens['bedroom'], expired['session_id'], 1, expired_turn)
        self.store.conn.execute('UPDATE room_sessions SET expires_at=0')
        self.store.conn.commit()
        with self.assertRaisesRegex(HandoffDenied, 'stale_session'):
            self.hub.validate_claim(self.tokens['bedroom'], expired['session_id'], 1, expired_turn)

    def test_rotation_and_revocation_remove_invitation(self):
        for rotate in (True, False):
            session = self.start()
            self.hub.claim(self.tokens['bedroom'], session['session_id'], 1, str(uuid.uuid4()))
            if rotate:
                _, token = self.store.enroll_sensor_node(self.user, 'bedroom', 'Bedroom', 'Bedroom')
                with self.assertRaises(HandoffDenied):
                    self.hub.claim(self.tokens['bedroom'], session['session_id'], 1, str(uuid.uuid4()))
                self.tokens['bedroom'] = token
                self.store.touch_sensor_node(self.user, 'bedroom')
            else:
                self.store.revoke_sensor_node(self.user, 'bedroom')
            self.assertIsNone(self.hub.status(self.user))
            self.assertEqual(self.store.conn.execute('SELECT count(*) FROM room_reply_claims').fetchone()[0], 0)

    def test_concurrent_claims_have_one_winner(self):
        session = self.start()
        turn = str(uuid.uuid4())
        barrier = threading.Barrier(2)
        def reserve(_):
            store = AuraMemoryStore(self.path)
            try:
                barrier.wait(timeout=3)
                RoomHandoff(store).claim(self.tokens['bedroom'], session['session_id'], 1, turn)
                return 'won'
            except HandoffDenied as exc:
                return str(exc)
            finally:
                store.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(reserve, range(2)), ['won', 'turn_already_claimed'])

    def test_invalid_turn_generation_and_capacity(self):
        session = self.start()
        for turn in (None, 1, '', 'not-a-uuid'):
            with self.assertRaisesRegex(HandoffDenied, 'invalid_turn'):
                self.hub.claim(self.tokens['bedroom'], session['session_id'], 1, turn)
        for generation in (True, '1', None):
            with self.assertRaises(HandoffDenied):
                self.hub.claim(self.tokens['bedroom'], session['session_id'], generation, str(uuid.uuid4()))
        with patch.object(self.hub, 'MAX_CLAIMS', 1):
            self.hub.claim(self.tokens['bedroom'], session['session_id'], 1, str(uuid.uuid4()))
            with self.assertRaisesRegex(HandoffDenied, 'session_capacity_reached'):
                self.hub.claim(self.tokens['bedroom'], session['session_id'], 1, str(uuid.uuid4()))

    def test_http_roles_consent_and_handoff(self):
        self.store.conn.close()
        self.store.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.store.conn.row_factory = sqlite3.Row
        self.store.conn.execute('PRAGMA foreign_keys=ON')
        server = HTTPServer(('127.0.0.1', 0), AuraSensorAPIHandler)
        server.aura_store = self.store
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        admin = 'a' * 40
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def post(path, body, token):
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/rooms/{path}',
                data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'X-AURA-API-Token': token})
            try:
                response = opener.open(request, timeout=10)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, json.loads(response.read())
        try:
            with opener.open(f'http://127.0.0.1:{server.server_port}/dashboard') as response:
                self.assertIn('/static/room-invitation.js', response.read().decode())
            with opener.open(f'http://127.0.0.1:{server.server_port}/static/room-invitation.js') as response:
                self.assertEqual(response.headers.get_content_type(), 'application/javascript')
                self.assertIn('redirect: "error"', response.read().decode())
            with patch.dict(os.environ, {'AURA_SENSOR_API_TOKEN': admin}), patch('api.sensor_api_server.beat_sensor_api_heartbeat'):
                self.assertEqual(post('start', {}, '')[0], 401)
                self.assertEqual(post('start', {'approved': True}, self.tokens['bedroom'])[0], 401)
                self.assertEqual(post('start', {'node_id': 'bedroom', 'approved': 'true'}, admin)[0], 409)
                with (
                    patch.object(room_invitation, 'load_env_file'),
                    patch('builtins.input', return_value='INVITE bedroom'),
                    redirect_stdout(StringIO()),
                ):
                    self.assertEqual(room_invitation.main([
                        '--hub-url', f'http://127.0.0.1:{server.server_port}',
                        'start', 'bedroom',
                    ]), 0)
                session = post('status', {}, admin)[1]['session']
                claim = {'session_id': session['session_id'], 'generation': 1, 'turn_id': str(uuid.uuid4())}
                self.assertEqual(post('claim', claim, admin)[0], 401)
                self.assertEqual(post('claim/validate', claim, admin)[0], 401)
                self.assertEqual(post('claim', claim, self.tokens['kitchen'])[0], 409)
                client_turn = str(uuid.uuid4())
                with (
                    patch.object(pi_node_simulator, 'load_env_file'),
                    patch.dict(os.environ, {'AURA_SENSOR_NODE_TOKEN': self.tokens['bedroom']}),
                    redirect_stdout(StringIO()),
                ):
                    self.assertEqual(pi_node_simulator.claim_invited_room_turn(
                        session['session_id'], 1, client_turn,
                        f'http://127.0.0.1:{server.server_port}',
                    ), 0)
                client_claim = {'session_id': session['session_id'], 'generation': 1, 'turn_id': client_turn}
                self.assertEqual(post('claim', client_claim, self.tokens['bedroom'])[0], 409)
                self.assertEqual(post('claim', claim, self.tokens['bedroom'])[0], 200)
                self.assertEqual(post('claim/validate', claim, self.tokens['bedroom'])[0], 200)
                self.assertEqual(post('claim', claim, self.tokens['bedroom'])[0], 409)
                with (
                    patch.object(room_invitation, 'load_env_file'),
                    patch('builtins.input', return_value='TRANSFER kitchen'),
                    redirect_stdout(StringIO()),
                ):
                    self.assertEqual(room_invitation.main([
                        '--hub-url', f'http://127.0.0.1:{server.server_port}',
                        'transfer', session['session_id'], '1', 'kitchen',
                    ]), 0)
                self.assertEqual(post('claim', claim, self.tokens['bedroom'])[0], 409)
                self.assertEqual(post('claim/validate', claim, self.tokens['bedroom'])[0], 409)
                with (
                    patch.object(room_invitation, 'load_env_file'),
                    patch('builtins.input', return_value=f"STOP {session['session_id']}"),
                    redirect_stdout(StringIO()),
                ):
                    self.assertEqual(room_invitation.main([
                        '--hub-url', f'http://127.0.0.1:{server.server_port}',
                        'stop', session['session_id'], '2',
                    ]), 0)
                self.assertIsNone(post('status', {}, admin)[1]['session'])
                self.assertEqual(self.store.conn.execute('SELECT count(*) FROM conversation_logs').fetchone()[0], 0)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
