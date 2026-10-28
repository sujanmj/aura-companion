"""Expiry is opt-in, owner-scoped, and applied before recall/export."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memory.sqlite_store import AuraMemoryStore

class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'memory.db'
        self.store = AuraMemoryStore(self.path)
        self.store.apply_schema()
        self.owner = self.store.create_user('Owner')
        self.other = self.store.create_user('Other')
        for user in (self.owner, self.other):
            self.store.add_observation(user, 'event_note', 'old keys note', source='user_correction')
        self.store.conn.execute("UPDATE observations SET created_at=datetime('now', '-31 days')")
        self.store.conn.commit()
        self.store.add_observation(self.owner, 'scene', 'recent scene')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_default_and_preview_do_not_delete(self):
        self.assertEqual(self.store.observation_retention(self.owner), {'days': 0})
        self.assertEqual(self.store.preview_observation_expiry(self.owner, 30)['expiring'], 1)
        self.assertEqual(len(self.store.get_latest_observations(self.owner)), 2)
        self.store.apply_schema()  # An upgrade preserves records and policy.
        self.assertEqual(len(self.store.export_user_memory(self.owner)['records']['observations']), 2)

    def test_opt_in_removes_only_expired_owner_notes_and_persists(self):
        self.store.remember_fact(self.owner, 'drink', 'tea')
        self.assertEqual(self.store.set_observation_retention(self.owner, 30)['deleted'], 1)
        self.assertEqual(len(self.store.get_latest_observations(self.owner)), 1)
        self.assertEqual(len(self.store.get_latest_observations(self.other)), 1)
        self.store.close()
        self.store = AuraMemoryStore(self.path)
        self.store.apply_schema()
        self.assertEqual(self.store.observation_retention(self.owner)['days'], 30)
        self.store.conn.execute("UPDATE observations SET created_at=datetime('now', '-31 days')")
        self.store.conn.commit()
        exported = self.store.export_user_memory(self.owner)['records']
        self.assertEqual(exported['observations'], [])
        self.assertEqual(len(exported['memory_facts']), 1)
        self.assertEqual(exported['observation_retention'][0]['days'], 30)

    def test_recall_expires_and_disabling_preserves_remaining_notes(self):
        self.store.set_observation_retention(self.owner, 1)
        self.store.conn.execute("UPDATE observations SET created_at=datetime('now', '-2 days')")
        self.store.conn.commit()
        self.assertEqual(self.store.get_latest_observations(self.owner), [])
        self.store.add_observation(self.owner, 'event_note', 'new')
        self.store.set_observation_retention(self.owner, 0)
        self.store.conn.execute("UPDATE observations SET created_at=datetime('now', '-400 days')")
        self.store.conn.commit()
        self.assertEqual(len(self.store.get_latest_observations(self.owner)), 1)

    def test_invalid_values_cannot_change_policy_or_memory(self):
        for days in (True, False, -1, 2, 30.0, '30', None, 366):
            with self.assertRaises(ValueError):
                self.store.set_observation_retention(self.owner, days)
        self.assertEqual(self.store.observation_retention(self.owner)['days'], 0)
        self.assertEqual(len(self.store.get_latest_observations(self.owner)), 2)

if __name__ == '__main__':
    unittest.main()
