"""Expired conversation rows also clear pending sync work and queue remote deletion."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "aura-app" / "server"))

from memory_worker import (
    expire_conversations_with_cloud_cleanup,
    set_conversation_retention_with_cloud_cleanup,
)


class ConversationRetentionServiceTests(unittest.TestCase):
    def test_periodic_expiry_removes_pending_uploads_and_queues_remote_deletes(self):
        events = []
        store = Mock()
        store.get_expired_conversation_ids.return_value = [12, 15]
        store.expire_conversations.side_effect = lambda *_args, **_kwargs: events.append("delete-local") or 2
        with patch("memory_worker.discard_pending_conversations", side_effect=lambda ids: events.append(("discard", ids))), patch(
            "memory_worker.enqueue_conversation_deletions", side_effect=lambda ids: events.append(("queue-delete", ids))
        ):
            self.assertEqual(expire_conversations_with_cloud_cleanup(store, 7), 2)
        self.assertEqual(events, ["delete-local", ("discard", [12, 15]), ("queue-delete", [12, 15])])

    def test_setting_retention_queues_only_rows_deleted_by_the_new_policy(self):
        events = []
        store = Mock()
        store.get_expired_conversation_ids.return_value = [22]
        store.set_conversation_retention.return_value = {"days": 30, "deleted": 1}
        with patch("memory_worker.discard_pending_conversations", side_effect=lambda ids: events.append(("discard", ids))), patch(
            "memory_worker.enqueue_conversation_deletions", side_effect=lambda ids: events.append(("queue-delete", ids))
        ):
            result = set_conversation_retention_with_cloud_cleanup(store, 7, 30)
        self.assertEqual(result, {"days": 30, "deleted": 1})
        self.assertEqual(events, [("discard", [22]), ("queue-delete", [22])])

    def test_no_expired_rows_do_not_touch_cloud_outbox(self):
        store = Mock()
        store.get_expired_conversation_ids.return_value = []
        with patch("memory_worker.discard_pending_conversations") as discard, patch(
            "memory_worker.enqueue_conversation_deletions"
        ) as enqueue:
            self.assertEqual(expire_conversations_with_cloud_cleanup(store, 7), 0)
        discard.assert_not_called()
        enqueue.assert_not_called()
        store.expire_conversations.assert_not_called()


if __name__ == "__main__":
    unittest.main()
