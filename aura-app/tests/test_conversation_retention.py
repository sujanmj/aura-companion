"""Conversation expiry is explicit, owner-scoped, and separate from memory facts."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from memory.sqlite_store import AuraMemoryStore


class ConversationRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.db"
        self.store = AuraMemoryStore(self.path)
        self.store.apply_schema()
        self.owner = self.store.get_or_create_user("Owner")
        self.other = self.store.get_or_create_user("Other")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_default_preview_and_opt_in_expiry_preserve_other_memory_and_owners(self):
        old_user = self.store.add_conversation(self.owner, "user", "Old question")
        old_assistant = self.store.add_conversation(self.owner, "assistant", "Old answer")
        self.store.add_conversation(self.owner, "user", "Recent question")
        other_old = self.store.add_conversation(self.other, "user", "Other account history")
        self.store.conn.execute(
            "UPDATE conversation_logs SET created_at=datetime('now', '-31 days') WHERE id IN (?, ?, ?)",
            (old_user, old_assistant, other_old),
        )
        self.store.conn.commit()
        self.store.remember_fact(self.owner, "favorite_drink", "tea")

        self.assertEqual(self.store.conversation_retention(self.owner), {"days": 0})
        self.assertEqual(self.store.preview_conversation_expiry(self.owner, 30), {
            "days": 30, "expiring": 2,
        })
        self.assertEqual(len(self.store.get_recent_conversations(self.owner, limit=20)), 3)
        self.assertEqual(self.store.set_conversation_retention(self.owner, 30), {
            "days": 30, "deleted": 2,
        })
        exported = self.store.export_user_memory(self.owner)["records"]
        self.assertEqual([row["message"] for row in exported["conversation_logs"]], ["Recent question"])
        self.assertEqual(exported["conversation_retention"][0]["days"], 30)
        self.assertEqual(self.store.get_recent_conversations(self.other, limit=20)[0]["message"], "Other account history")
        self.assertEqual(self.store.get_memory_facts(self.owner)[0]["fact_value"], "tea")

    def test_expiry_runs_before_recall_and_survives_restart(self):
        message_id = self.store.add_conversation(self.owner, "user", "Private history")
        self.store.set_conversation_retention(self.owner, 1)
        self.store.conn.execute(
            "UPDATE conversation_logs SET created_at=datetime('now', '-2 days') WHERE id=?",
            (message_id,),
        )
        self.store.conn.commit()
        self.assertEqual(self.store.get_recent_conversations(self.owner), [])
        self.store.close()
        self.store = AuraMemoryStore(self.path)
        self.store.apply_schema()
        self.assertEqual(self.store.conversation_retention(self.owner), {"days": 1})
        self.assertEqual(self.store.export_user_memory(self.owner)["records"]["conversation_logs"], [])

    def test_invalid_values_do_not_change_policy_or_delete_history(self):
        self.store.add_conversation(self.owner, "user", "Keep this history")
        for days in (True, False, -1, 2, 30.0, "30", None, 366):
            with self.subTest(days=days), self.assertRaises(ValueError):
                self.store.set_conversation_retention(self.owner, days)
        self.assertEqual(self.store.conversation_retention(self.owner), {"days": 0})
        self.assertEqual(len(self.store.get_recent_conversations(self.owner)), 1)


if __name__ == "__main__":
    unittest.main()
