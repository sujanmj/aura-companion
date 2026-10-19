"""Memory correction/deletion is explicit and always scoped to its owner."""
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from memory.sqlite_store import AuraMemoryStore

class MemoryControlsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AuraMemoryStore(Path(self.temp.name) / 'memory.db')
        self.store.apply_schema()
        self.owner = self.store.get_or_create_user('Owner')
        self.other = self.store.get_or_create_user('Other')
        self.store.remember_fact(self.owner, 'favorite_drink', 'tea')
        self.fact_id = self.store.conn.execute('SELECT id FROM memory_facts WHERE user_id=?', (self.owner,)).fetchone()['id']
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()
    def test_owner_can_correct_and_then_forget_fact(self):
        self.assertTrue(self.store.update_memory_fact(self.owner, self.fact_id, 'masala chai'))
        fact = self.store.get_memory_facts(self.owner)[0]
        self.assertEqual(fact['fact_value'], 'masala chai')
        self.assertEqual(fact['source'], 'user_correction')
        self.assertTrue(self.store.delete_memory_fact(self.owner, self.fact_id))
        self.assertEqual(self.store.get_memory_facts(self.owner), [])
        self.store.remember_fact(self.owner, 'favorite_drink', 'tea again', source='conversation')
        self.assertEqual(self.store.get_memory_facts(self.owner), [])
        self.store.remember_fact(self.owner, 'favorite_drink', 'please remember tea', source='user_correction')
        self.assertEqual(self.store.get_memory_facts(self.owner)[0]['fact_value'], 'please remember tea')
    def test_other_users_facts_cannot_be_changed_or_deleted(self):
        self.assertFalse(self.store.update_memory_fact(self.other, self.fact_id, 'changed'))
        self.assertFalse(self.store.delete_memory_fact(self.other, self.fact_id))
        self.assertEqual(self.store.get_memory_facts(self.owner)[0]['fact_value'], 'tea')
    def test_invalid_corrections_leave_fact_unchanged(self):
        for value in ('', '  ', 'x' * 2001):
            with self.assertRaises(ValueError):
                self.store.update_memory_fact(self.owner, self.fact_id, value)
        self.assertEqual(self.store.get_memory_facts(self.owner)[0]['fact_value'], 'tea')
    def test_missing_fact_is_safe(self):
        self.assertFalse(self.store.update_memory_fact(self.owner, 9999, 'new'))
        self.assertFalse(self.store.delete_memory_fact(self.owner, 9999))

if __name__ == '__main__': unittest.main()
