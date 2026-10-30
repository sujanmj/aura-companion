"""Local SQLite backups are verifiable, private files with explicit deletion."""
from pathlib import Path
from contextlib import contextmanager
import os
import sqlite3
import stat
import sys
import tempfile
import unittest

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER_DIR))
from backup_manager import (
    create_database_backup,
    delete_database_backup,
    list_database_backups,
    verify_database_backup,
)


@contextmanager
def _connect(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class BackupManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "memory.db"
        with _connect(self.database) as store:
            store.execute("CREATE TABLE memory (note TEXT NOT NULL)")
            store.execute("INSERT INTO memory VALUES (?)", ("private saved note",))

    def tearDown(self):
        self.temp.cleanup()

    def test_create_verifies_a_standalone_backup_without_changing_the_database(self):
        backup = create_database_backup(self.database)
        self.assertRegex(backup["name"], r"^aura-\d{8}T\d{12}\.db$")
        backup_path = self.root / "backups" / backup["name"]
        self.assertEqual(backup_path.stat().st_size, backup["size_bytes"])
        with _connect(backup_path) as restored:
            self.assertEqual(restored.execute("PRAGMA quick_check").fetchone()[0], "ok")
            self.assertEqual(
                restored.execute("SELECT note FROM memory").fetchone()[0],
                "private saved note",
            )
        with _connect(self.database) as active:
            self.assertEqual(active.execute("SELECT count(*) FROM memory").fetchone()[0], 1)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(backup_path.stat().st_mode), 0o600)

    def test_backup_includes_committed_wal_rows_without_replacing_the_live_database(self):
        active = sqlite3.connect(self.database)
        try:
            active.execute("PRAGMA journal_mode=WAL")
            active.execute("INSERT INTO memory VALUES (?)", ("committed wal note",))
            active.commit()
            backup = create_database_backup(self.database)
            with _connect(self.root / "backups" / backup["name"]) as snapshot:
                self.assertEqual(
                    snapshot.execute("SELECT count(*) FROM memory WHERE note=?", ("committed wal note",)).fetchone()[0],
                    1,
                )
            self.assertEqual(
                active.execute("SELECT count(*) FROM memory WHERE note=?", ("committed wal note",)).fetchone()[0],
                1,
            )
        finally:
            active.close()

    def test_existing_snapshot_can_be_verified_read_only(self):
        backup = create_database_backup(self.database)
        result = verify_database_backup(self.database, backup["name"])
        self.assertEqual(result["name"], backup["name"])
        self.assertEqual(result["size_bytes"], backup["size_bytes"])
        self.assertEqual(result["integrity"], "ok")
        self.assertRegex(result["checked_at"], r"Z$")
        with _connect(self.database) as active:
            self.assertEqual(active.execute("SELECT note FROM memory").fetchone()[0], "private saved note")

    def test_verification_rejects_invalid_names_symlinks_and_corrupt_files(self):
        for name in ("../memory.db", "not-a-backup.db", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify_database_backup(self.database, name)

        backup_dir = self.root / "backups"
        backup_dir.mkdir()
        corrupt = "aura-20261030T091700000000.db"
        (backup_dir / corrupt).write_text("not sqlite")
        with self.assertRaisesRegex(ValueError, "integrity check"):
            verify_database_backup(self.database, corrupt)

    @unittest.skipUnless(os.name == "posix", "symlink creation is not portable on Windows")
    def test_verification_refuses_symlinked_snapshot_and_directory(self):
        outside = self.root / "outside.db"
        outside.write_bytes(self.database.read_bytes())
        name = "aura-20261030T091700000000.db"
        backup_dir = self.root / "backups"
        backup_dir.mkdir()
        (backup_dir / name).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "regular file"):
            verify_database_backup(self.database, name)
        self.assertTrue(outside.exists())

    def test_inventory_hides_nonbackup_files_and_delete_removes_only_exact_snapshot(self):
        first = create_database_backup(self.database)
        second = create_database_backup(self.database)
        backup_dir = self.root / "backups"
        (backup_dir / "notes.txt").write_text("not a backup")
        inventory = list_database_backups(self.database)
        self.assertEqual([item["name"] for item in inventory], [second["name"], first["name"]])
        self.assertTrue(delete_database_backup(self.database, first["name"]))
        self.assertFalse(delete_database_backup(self.database, first["name"]))
        self.assertEqual([item["name"] for item in list_database_backups(self.database)], [second["name"]])
        self.assertTrue((backup_dir / "notes.txt").exists())
        with _connect(self.database) as active:
            self.assertEqual(active.execute("SELECT note FROM memory").fetchone()[0], "private saved note")

    def test_delete_rejects_untrusted_names_before_touching_the_backup_directory(self):
        for name in (
            "../memory.db",
            "aura-20261030T091700000000.db/../../memory.db",
            "aura-20261030T091700000000.sqlite",
            None,
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                delete_database_backup(self.database, name)
        self.assertFalse((self.root / "memory.db").is_symlink())

    @unittest.skipUnless(os.name == "posix", "symlink creation is not portable on Windows")
    def test_inventory_and_delete_ignore_a_symlinked_snapshot(self):
        outside = self.root / "outside.db"
        outside.write_text("keep this file")
        backup_dir = self.root / "backups"
        backup_dir.mkdir()
        name = "aura-20261030T091700000000.db"
        (backup_dir / name).symlink_to(outside)
        self.assertEqual(list_database_backups(self.database), [])
        self.assertFalse(delete_database_backup(self.database, name))
        self.assertEqual(outside.read_text(), "keep this file")

    @unittest.skipUnless(os.name == "posix", "symlink creation is not portable on Windows")
    def test_inventory_and_delete_refuse_a_symlinked_backup_directory(self):
        outside = self.root / "outside"
        outside.mkdir()
        name = "aura-20261030T091700000000.db"
        (outside / name).write_text("keep this file")
        (self.root / "backups").symlink_to(outside, target_is_directory=True)
        self.assertEqual(list_database_backups(self.database), [])
        self.assertFalse(delete_database_backup(self.database, name))
        self.assertEqual((outside / name).read_text(), "keep this file")


if __name__ == "__main__":
    unittest.main()
