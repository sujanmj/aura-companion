"""User-entered person memories require consent and remain owner-scoped."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from memory.sqlite_store import AuraMemoryStore


class PersonMemoryNotesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AuraMemoryStore(Path(self.temp.name) / "memory.db")
        self.store.apply_schema()
        self.owner = self.store.get_or_create_user("Owner")
        self.other = self.store.get_or_create_user("Other")
        self.person = self.store.add_known_person(
            self.owner,
            "Taylor",
            relation="friend",
            consent_to_remember=True,
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_note_requires_per_note_confirmation_and_consented_person(self):
        with self.assertRaisesRegex(ValueError, "Invalid person"):
            self.store.add_person_memory_note(
                self.owner, True, "We went to the park.", True
            )
        with self.assertRaises(ValueError):
            self.store.add_person_memory_note(
                self.owner, self.person, "We went to the park.", False
            )
        with self.assertRaises(ValueError):
            self.store.add_person_memory_note(
                self.owner, self.person, "We went to the park.", 1
            )
        unconsented = self.store.add_known_person(self.owner, "Morgan")
        with self.assertRaisesRegex(ValueError, "Consented person"):
            self.store.add_person_memory_note(
                self.owner, unconsented, "We went to the park.", True
            )
        self.assertEqual(self.store.get_recent_person_events(self.owner), [])

    def test_note_is_explicit_and_owner_scoped_for_delete_and_export(self):
        event_id = self.store.add_person_memory_note(
            self.owner, self.person, "We went to the park.", True
        )
        note = self.store.get_recent_person_events(self.owner)[0]
        self.assertEqual(note["event_type"], "user_memory_note")
        self.assertEqual(note["source"], "user_explicit")
        self.assertEqual(note["confidence"], 1.0)
        self.assertEqual(note["display_name"], "Taylor")
        self.assertFalse(self.store.delete_person_memory_note(self.other, event_id))
        self.assertFalse(self.store.delete_person_memory_note(self.owner, True))
        exported = self.store.export_user_memory(self.owner)
        self.assertEqual(exported["records"]["person_events"][0]["event_summary"], "We went to the park.")
        self.assertTrue(self.store.delete_person_memory_note(self.owner, event_id))
        self.assertEqual(self.store.get_recent_person_events(self.owner), [])

    def test_note_length_is_bounded_and_person_forget_removes_note(self):
        for note in ("", "  ", "x" * 501):
            with self.subTest(size=len(note)):
                with self.assertRaises(ValueError):
                    self.store.add_person_memory_note(
                        self.owner, self.person, note, True
                    )
        self.store.add_person_memory_note(
            self.owner, self.person, "We went to the park.", True
        )
        self.assertTrue(self.store.forget_known_person(self.owner, self.person))
        self.assertEqual(self.store.get_recent_person_events(self.owner), [])


if __name__ == "__main__":
    unittest.main()
