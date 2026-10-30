"""Offline tests for optional, server-side Supabase record sync."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cloud.supabase_sync import (
    discard_pending_conversations,
    enqueue_conversation_deletions,
    flush_pending,
    sync_conversation,
    sync_sensor_event,
)
from memory.sqlite_store import AuraMemoryStore


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class CloudSyncTests(unittest.TestCase):
    def test_missing_settings_leave_local_app_offline(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "cloud.supabase_sync.urllib.request.urlopen"
        ) as open_url:
            self.assertFalse(sync_conversation(1, "user", "hello", "2026-01-01T00:00:00Z"))
            self.assertFalse(sync_sensor_event({"event_id": 1, "event_type": "fire"}))
            open_url.assert_not_called()

    def test_conversation_sync_keeps_key_in_server_request(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "memory.db"
            store = AuraMemoryStore(db)
            store.apply_schema()
            user = store.get_or_create_user("Owner")
            row_id = store.add_conversation(user, "assistant", "Hello")
            settings = self._settings(db)
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", return_value=FakeResponse()
            ) as open_url:
                self.assertTrue(sync_conversation(row_id, "assistant", "Hello", "2026-01-01T00:00:00Z"))
            request = open_url.call_args.args[0]
            self.assertIn("aura_conversations?on_conflict=device_id,local_id", request.full_url)
            self.assertEqual(request.get_header("Authorization"), "Bearer server-secret")
            self.assertEqual(json.loads(request.data)["device_id"], "aura-pi-main")
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM cloud_sync_outbox").fetchone()[0], 0)
            store.close()

    def test_failed_sync_queues_only_a_reference_then_retries_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "memory.db"
            store = AuraMemoryStore(db)
            store.apply_schema()
            user = store.get_or_create_user("Owner")
            message = "private-message-sentinel"
            row_id = store.add_conversation(user, "user", message)
            settings = self._settings(db)
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", side_effect=OSError("offline")
            ):
                self.assertFalse(sync_conversation(row_id, "user", message, "2026-01-01T00:00:00Z"))

            queued = store.conn.execute(
                "SELECT record_type, local_id, device_id, attempts FROM cloud_sync_outbox"
            ).fetchall()
            self.assertEqual([tuple(row) for row in queued], [("conversation", row_id, "aura-pi-main", 0)])
            self.assertNotIn("message", [row[1] for row in store.conn.execute("PRAGMA table_info(cloud_sync_outbox)")])

            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", side_effect=OSError("offline")
            ):
                self.assertEqual(flush_pending(now=1_000), 0)
            retry = store.conn.execute(
                "SELECT attempts, next_attempt_at FROM cloud_sync_outbox"
            ).fetchone()
            self.assertEqual(tuple(retry), (1, 1_060))
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", return_value=FakeResponse()
            ) as open_url:
                self.assertEqual(flush_pending(now=1_059), 0)
                open_url.assert_not_called()
                self.assertEqual(flush_pending(now=1_060), 1)
            payload = json.loads(open_url.call_args.args[0].data)
            self.assertEqual(payload["message"], message)
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM cloud_sync_outbox").fetchone()[0], 0)
            store.close()

    def test_erased_conversations_are_removed_and_remote_deletion_is_queued(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "memory.db"
            store = AuraMemoryStore(db)
            store.apply_schema()
            user = store.get_or_create_user("Owner")
            row_id = store.add_conversation(user, "user", "private-message-sentinel")
            settings = self._settings(db)
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", side_effect=OSError("offline")
            ):
                self.assertFalse(sync_conversation(row_id, "user", "private-message-sentinel", "2026-01-01T00:00:00Z"))
            store.clear_conversation_history(user)
            with patch.dict(os.environ, settings, clear=True):
                discard_pending_conversations([row_id])
                enqueue_conversation_deletions([row_id])
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen"
                , return_value=FakeResponse()
            ) as open_url:
                self.assertEqual(flush_pending(now=1_000), 1)
                request = open_url.call_args.args[0]
                self.assertEqual(request.method, "DELETE")
                self.assertNotIn("private-message-sentinel", request.full_url)
                self.assertIsNone(request.data)
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM cloud_sync_outbox").fetchone()[0], 0)
            late_id = store.add_conversation(user, "user", "message-cleared-before-sync")
            store.clear_conversation_history(user)
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen"
            ) as open_url:
                self.assertFalse(sync_conversation(late_id, "user", "message-cleared-before-sync", "2026-01-01T00:00:00Z"))
                open_url.assert_not_called()
            store.close()

    def test_failed_sensor_event_sync_retries_from_its_source_row(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "memory.db"
            store = AuraMemoryStore(db)
            store.apply_schema()
            user = store.get_or_create_user("Owner")
            event_id = store.add_device_event(
                user, "sensor_state_changed", "A configured sensor changed state.",
                source="pi_bedroom_node", room="bedroom", confidence=0.9,
            )
            event = {
                "event_id": event_id,
                "event_type": "sensor_state_changed",
                "event_summary": "A configured sensor changed state.",
            }
            settings = self._settings(db)
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", side_effect=OSError("offline")
            ):
                self.assertFalse(sync_sensor_event(event))
            self.assertEqual(
                tuple(store.conn.execute(
                    "SELECT record_type, local_id FROM cloud_sync_outbox"
                ).fetchone()),
                ("sensor_event", event_id),
            )
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", return_value=FakeResponse()
            ) as open_url:
                self.assertEqual(flush_pending(now=1_000), 1)
            payload = json.loads(open_url.call_args.args[0].data)
            self.assertEqual(payload["room"], "bedroom")
            self.assertEqual(payload["event_summary"], event["event_summary"])
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM cloud_sync_outbox").fetchone()[0], 0)
            store.close()

    def test_retry_batch_releases_database_write_lock_between_network_calls(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "memory.db"
            store = AuraMemoryStore(db)
            store.apply_schema()
            user = store.get_or_create_user("Owner")
            row_ids = [
                store.add_conversation(user, "user", f"message-{index}")
                for index in range(2)
            ]
            settings = self._settings(db)
            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", side_effect=OSError("offline")
            ):
                for row_id in row_ids:
                    self.assertFalse(sync_conversation(row_id, "user", "placeholder", ""))

            requests = []

            def write_local_memory_during_second_request(_request, timeout):
                requests.append(_request)
                if len(requests) == 2:
                    concurrent = sqlite3.connect(db, timeout=0.05)
                    try:
                        concurrent.execute(
                            "INSERT INTO conversation_logs(user_id, role, message) VALUES (?, 'user', 'concurrent write')",
                            (user,),
                        )
                        concurrent.commit()
                    finally:
                        concurrent.close()
                return FakeResponse()

            with patch.dict(os.environ, settings, clear=True), patch(
                "cloud.supabase_sync.urllib.request.urlopen", side_effect=write_local_memory_during_second_request
            ):
                self.assertEqual(flush_pending(now=1_000), 2)
            self.assertEqual(len(requests), 2)
            self.assertEqual(
                store.conn.execute("SELECT COUNT(*) FROM conversation_logs WHERE message='concurrent write'").fetchone()[0],
                1,
            )
            store.close()

    def test_rejects_non_https_cloud_endpoint(self) -> None:
        settings = {
            "AURA_SUPABASE_URL": "http://example.supabase.co",
            "AURA_SUPABASE_SERVICE_ROLE_KEY": "server-secret",
            "AURA_CLOUD_DEVICE_ID": "aura-pi-main",
        }
        with patch.dict(os.environ, settings, clear=True), patch(
            "cloud.supabase_sync.urllib.request.urlopen"
        ) as open_url:
            self.assertFalse(sync_sensor_event({"event_id": 1, "event_type": "fire", "event_summary": "test"}))
            open_url.assert_not_called()

    @staticmethod
    def _settings(db: Path) -> dict[str, str]:
        return {
            "AURA_DB_PATH": str(db),
            "AURA_SUPABASE_URL": "https://example.supabase.co",
            "AURA_SUPABASE_SERVICE_ROLE_KEY": "server-secret",
            "AURA_CLOUD_DEVICE_ID": "aura-pi-main",
        }


if __name__ == "__main__":
    unittest.main()
