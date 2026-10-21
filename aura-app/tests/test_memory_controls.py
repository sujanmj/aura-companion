"""Memory correction/deletion is explicit and always scoped to its owner."""
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
    def test_forgetting_a_person_removes_their_timeline_and_is_owner_scoped(self):
        person_id = self.store.add_known_person(
            self.owner, 'Alex', relation='friend', consent_to_remember=True
        )
        other_person_id = self.store.add_known_person(self.other, 'Taylor')
        self.store.add_person_event(
            self.owner, person_id, 'person_introduced', 'Alex was introduced.'
        )
        self.store.add_person_event(
            self.other, other_person_id, 'person_introduced', 'Taylor was introduced.'
        )
        self.assertFalse(self.store.forget_known_person(self.other, person_id))
        self.assertTrue(self.store.get_known_people(self.owner))
        self.assertTrue(self.store.forget_known_person(self.owner, person_id))
        self.assertEqual(self.store.get_known_people(self.owner), [])
        self.assertEqual(self.store.get_recent_person_events(self.owner), [])
        self.assertEqual(self.store.get_known_people(self.other)[0]['display_name'], 'Taylor')
        self.assertEqual(
            self.store.get_recent_person_events(self.other)[0]['event_summary'],
            'Taylor was introduced.',
        )
    def test_daily_reminders_are_once_per_local_day_and_owner_scoped(self):
        reminder_id = self.store.add_routine_reminder(
            self.owner, 'Take medication', '20:00'
        )
        other_id = self.store.add_routine_reminder(
            self.other, 'Feed the cat', '19:00'
        )
        day = datetime(2026, 10, 21, 20, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        before = self.store.create_due_routine_reminder(
            self.owner, day - timedelta(minutes=1)
        )
        self.assertIsNone(before)
        due = self.store.create_due_routine_reminder(self.owner, day)
        self.assertEqual(due['reminder_id'], reminder_id)
        self.assertIn('Take medication', due['response'])
        self.assertIn("can’t tell whether you’ve done it", due['response'])
        self.assertIsNone(self.store.create_due_routine_reminder(self.owner, day))
        self.assertFalse(self.store.dismiss_routine_reminder(self.other, reminder_id, day))
        self.assertTrue(self.store.dismiss_routine_reminder(self.owner, reminder_id, day))
        reminders = self.store.get_routine_reminders(self.owner)
        self.assertEqual(reminders[0]['dismissed_on'], '2026-10-21')
        self.assertEqual(self.store.get_routine_reminders(self.other)[0]['id'], other_id)
        self.assertFalse(self.store.delete_routine_reminder(self.other, reminder_id))
        self.assertTrue(self.store.delete_routine_reminder(self.owner, reminder_id))
        self.assertEqual(self.store.get_routine_reminders(self.owner), [])

    def test_daily_reminders_reject_invalid_values_and_repeat_tomorrow(self):
        for label, clock in (('', '09:00'), ('x' * 121, '09:00'), ('Water', '25:00')):
            with self.assertRaises(ValueError):
                self.store.add_routine_reminder(self.owner, label, clock)
        self.store.add_routine_reminder(self.owner, 'Walk', '09:30')
        first_day = datetime(2026, 10, 21, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertIsNotNone(self.store.create_due_routine_reminder(self.owner, first_day))
        next_day = first_day + timedelta(days=1)
        self.assertIsNotNone(self.store.create_due_routine_reminder(self.owner, next_day))
    def test_ambient_scene_saves_only_derived_summaries_and_rate_limits_changes(self):
        first = self.store.add_ambient_scene_observation(
            self.owner, ['living room', 'sofa'], True, 0.91
        )
        self.assertTrue(first['saved'])
        saved = self.store.get_latest_observations(self.owner)
        self.assertEqual(saved[0]['event_type'], 'ambient_visual_context')
        self.assertEqual(saved[0]['source'], 'mac_local_vision')
        self.assertEqual(saved[0]['confidence'], 0.91)
        self.assertNotIn('image', saved[0]['event_summary'].lower())

        unchanged = self.store.add_ambient_scene_observation(
            self.owner, ['living room', 'sofa'], True, 0.93
        )
        self.assertEqual(unchanged, {'saved': False, 'reason': 'unchanged'})
        limited = self.store.add_ambient_scene_observation(
            self.owner, ['kitchen', 'table'], False, 0.8
        )
        self.assertEqual(limited, {'saved': False, 'reason': 'rate_limited'})

        self.store.conn.execute(
            "UPDATE observations SET created_at=datetime('now', '-61 seconds') WHERE id=?",
            (first['observation_id'],),
        )
        self.store.conn.commit()
        changed = self.store.add_ambient_scene_observation(
            self.owner, ['kitchen', 'table'], False, 0.8
        )
        self.assertTrue(changed['saved'])
        self.assertEqual(len(self.store.get_latest_observations(self.owner)), 2)

    def test_ambient_scene_rejects_invalid_data_and_separates_users(self):
        for labels, present, confidence in (
            (['<script>'], True, 0.8),
            (['x'] * 5, True, 0.8),
            (['room'], 1, 0.8),
            (['room'], True, float('nan')),
        ):
            with self.assertRaises(ValueError):
                self.store.add_ambient_scene_observation(
                    self.owner, labels, present, confidence
                )
        observation = self.store.add_ambient_scene_observation(
            self.owner, ['room'], False, 0.6
        )
        self.assertFalse(
            self.store.delete_observation(self.other, observation['observation_id'])
        )
        self.assertEqual(self.store.get_latest_observations(self.owner)[0]['source'], 'mac_local_vision')
        self.assertEqual(self.store.get_latest_observations(self.other), [])

if __name__ == '__main__': unittest.main()
