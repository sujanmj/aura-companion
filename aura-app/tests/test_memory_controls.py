"""Memory correction/deletion is explicit and always scoped to its owner."""
from pathlib import Path
import sys
import tempfile
import unittest
import sqlite3
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

    def test_reminder_acknowledgement_records_seen_not_completion(self):
        reminder_id = self.store.add_routine_reminder(self.owner, 'Take medication', '20:00')
        day = datetime(2026, 10, 21, 20, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertFalse(self.store.acknowledge_routine_reminder(self.owner, reminder_id, day))
        self.assertFalse(self.store.acknowledge_routine_reminder(self.other, reminder_id, day))
        delivery = self.store.create_due_routine_reminder(self.owner, day)
        self.assertIn('neither action confirms completion or a dose', delivery['response'])
        self.assertTrue(self.store.acknowledge_routine_reminder(self.owner, reminder_id, day))
        self.assertTrue(self.store.acknowledge_routine_reminder(self.owner, reminder_id, day))
        self.assertFalse(self.store.dismiss_routine_reminder(self.owner, reminder_id, day))
        current = self.store.get_routine_reminders(self.owner)[0]
        self.assertEqual(current['acknowledged_on'], '2026-10-21')
        self.assertIsNone(current['dismissed_on'])
        exported = self.store.export_user_memory(self.owner)
        self.assertEqual(
            exported['records']['routine_reminders'][0]['acknowledged_on'], '2026-10-21'
        )
        tomorrow = day + timedelta(days=1)
        self.store.create_due_routine_reminder(self.owner, tomorrow)
        current = self.store.get_routine_reminders(self.owner)[0]
        self.assertIsNone(current['acknowledged_on'])
        self.assertIsNone(current['dismissed_on'])

    def test_daily_reminders_reject_invalid_values_and_repeat_tomorrow(self):
        for label, clock in (('', '09:00'), ('x' * 121, '09:00'), ('Water', '25:00')):
            with self.assertRaises(ValueError):
                self.store.add_routine_reminder(self.owner, label, clock)
        self.store.add_routine_reminder(self.owner, 'Walk', '09:30')
        first_day = datetime(2026, 10, 21, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertIsNotNone(self.store.create_due_routine_reminder(self.owner, first_day))
        next_day = first_day + timedelta(days=1)
        self.assertIsNotNone(self.store.create_due_routine_reminder(self.owner, next_day))

    def test_weekly_reminder_runs_only_on_selected_local_weekdays(self):
        reminder_id = self.store.add_routine_reminder(
            self.owner, 'Call clinic', '09:00', [1, 3, 5]
        )
        monday = datetime(2026, 10, 19, 9, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(self.store.create_due_routine_reminder(self.owner, monday)['reminder_id'], reminder_id)
        self.assertIsNone(self.store.create_due_routine_reminder(self.owner, monday + timedelta(days=1)))
        self.assertEqual(self.store.create_due_routine_reminder(self.owner, monday + timedelta(days=2))['reminder_id'], reminder_id)
        self.assertIsNone(self.store.create_due_routine_reminder(self.owner, monday + timedelta(days=3)))
        self.assertEqual(self.store.create_due_routine_reminder(self.owner, monday + timedelta(days=4))['reminder_id'], reminder_id)
        self.assertEqual(self.store.get_routine_reminders(self.owner)[0]['days_of_week'], '1,3,5')

    def test_weekly_reminder_rejects_empty_duplicate_and_out_of_range_days(self):
        for days in ([], [1, 1], [0], [8], [True]):
            with self.assertRaises(ValueError):
                self.store.add_routine_reminder(self.owner, 'Reminder', '09:00', days)

    def test_existing_daily_reminders_migrate_to_all_weekdays(self):
        legacy_path = Path(self.temp.name) / 'legacy.db'
        legacy = sqlite3.connect(legacy_path)
        legacy.executescript('''
            CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, preferred_name TEXT,
                comfort_style TEXT);
            INSERT INTO users (id, name) VALUES (1, 'Owner');
            CREATE TABLE routine_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                label TEXT NOT NULL, local_time TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, last_delivered_on TEXT,
                dismissed_on TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO routine_reminders (user_id, label, local_time)
                VALUES (1, 'Existing reminder', '08:00');
        ''')
        legacy.close()
        migrated = AuraMemoryStore(legacy_path)
        try:
            migrated.apply_schema()
            reminders = migrated.get_routine_reminders(1)
            self.assertEqual(len(reminders), 1)
            self.assertEqual(reminders[0]['label'], 'Existing reminder')
            self.assertEqual(reminders[0]['days_of_week'], '1,2,3,4,5,6,7')
            self.assertIsNone(reminders[0]['acknowledged_on'])
        finally:
            migrated.close()

    def test_daily_reminders_can_be_paused_and_reenabled_without_cross_user_access(self):
        reminder_id = self.store.add_routine_reminder(self.owner, 'Walk', '09:30')
        self.assertEqual(
            self.store.set_routine_reminder_enabled(self.other, reminder_id, False),
            'not_found',
        )
        self.assertIsNone(self.store.set_routine_reminder_enabled(self.owner, reminder_id, False))
        self.assertFalse(self.store.get_routine_reminders(self.owner)[0]['enabled'])
        due_time = datetime(2026, 10, 21, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertIsNone(self.store.create_due_routine_reminder(self.owner, due_time))
        self.assertIsNone(self.store.set_routine_reminder_enabled(self.owner, reminder_id, True))
        self.assertIsNotNone(self.store.create_due_routine_reminder(self.owner, due_time))
        with self.assertRaises(ValueError):
            self.store.set_routine_reminder_enabled(self.owner, reminder_id, 1)

    def test_reenabling_reminder_respects_active_reminder_limit(self):
        reminders = [
            self.store.add_routine_reminder(self.owner, f'Reminder {index}', '09:00')
            for index in range(20)
        ]
        self.assertIsNone(self.store.set_routine_reminder_enabled(self.owner, reminders[0], False))
        reminders.append(
            self.store.add_routine_reminder(self.owner, 'Reminder 20', '09:00')
        )
        self.assertEqual(
            self.store.set_routine_reminder_enabled(self.owner, reminders[0], True),
            'limit',
        )
        self.assertFalse(next(
            reminder for reminder in self.store.get_routine_reminders(self.owner)
            if reminder['id'] == reminders[0]
        )['enabled'])

    def test_observation_corrections_are_user_labeled_bounded_and_owner_scoped(self):
        observation_id = self.store.add_ambient_scene_observation(
            self.owner, ['sofa'], False, 0.8
        )['observation_id']
        self.assertFalse(
            self.store.correct_observation(self.other, observation_id, 'The keys are on the table.')
        )
        for value in ('', 'x' * 501):
            with self.assertRaises(ValueError):
                self.store.correct_observation(self.owner, observation_id, value)
        self.assertTrue(
            self.store.correct_observation(self.owner, observation_id, 'The keys are on the blue sofa.')
        )
        corrected = self.store.get_latest_observations(self.owner, limit=1)[0]
        self.assertEqual(corrected['source'], 'user_correction')
        self.assertEqual(corrected['event_type'], 'user_corrected_observation')
        self.assertEqual(corrected['confidence'], 1.0)
        self.assertEqual(corrected['event_summary'], 'User correction: The keys are on the blue sofa.')

    def test_clear_observations_only_removes_the_selected_users_observation_memory(self):
        self.store.add_observation(self.owner, 'user_explicit', 'Owner event note')
        self.store.add_observation(self.owner, 'ambient_context', 'Owner scene note')
        self.store.add_observation(self.other, 'user_explicit', 'Other event note')
        self.store.remember_fact(self.owner, 'favorite_drink', 'tea')
        self.store.add_routine_reminder(self.owner, 'Take medication', '20:00')

        self.assertEqual(self.store.clear_observations(self.owner), 2)
        self.assertEqual(self.store.get_latest_observations(self.owner), [])
        self.assertEqual(
            self.store.get_latest_observations(self.other)[0]['event_summary'],
            'Other event note',
        )
        self.assertEqual(self.store.get_memory_facts(self.owner)[0]['fact_value'], 'tea')
        self.assertEqual(self.store.get_routine_reminders(self.owner)[0]['label'], 'Take medication')
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
