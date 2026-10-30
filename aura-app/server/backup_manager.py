"""Safe inventory and explicit removal for AURA's local SQLite snapshots."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import sqlite3
import stat
import time


_BACKUP_NAME = re.compile(r"aura-\d{8}T\d{12}\.db\Z")


def _backup_directory(database_path: str | Path) -> Path:
    database = Path(database_path).expanduser().resolve()
    return database.parent / "backups"


def create_database_backup(database_path: str | Path) -> dict[str, int | str]:
    """Create and verify a new standalone snapshot without replacing older files."""
    database = Path(database_path).expanduser().resolve()
    if not database.is_file() or database.is_symlink():
        raise ValueError("AURA database is unavailable")
    directory = _backup_directory(database)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("AURA backup directory is unsafe")

    timestamp = datetime.now(timezone.utc)
    backup_path = None
    for _ in range(100):
        name = f"aura-{timestamp.strftime('%Y%m%dT%H%M%S%f')}.db"
        candidate = directory / name
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            backup_path = candidate
            break
        except FileExistsError:
            timestamp += timedelta(microseconds=1)
    if backup_path is None:
        raise OSError("Could not allocate a unique backup name")

    try:
        source = sqlite3.connect(database, timeout=10)
        destination = sqlite3.connect(backup_path, timeout=10)
        try:
            source.backup(destination)
            check = destination.execute("PRAGMA quick_check").fetchone()
            if not check or check[0] != "ok":
                raise sqlite3.DatabaseError("SQLite backup failed its integrity check")
            destination.commit()
        finally:
            destination.close()
            source.close()
        if os.name == "posix":
            os.chmod(backup_path, 0o600)
    except Exception:
        try:
            backup_path.unlink()
        except OSError:
            pass
        raise

    info = backup_path.stat()
    return {
        "name": backup_path.name,
        "size_bytes": info.st_size,
        "created_at": timestamp.isoformat().replace("+00:00", "Z"),
    }


def list_database_backups(database_path: str | Path) -> list[dict[str, int | str]]:
    """List only regular startup backups; never expose local filesystem paths."""
    directory = _backup_directory(database_path)
    try:
        if directory.is_symlink() or not directory.is_dir():
            return []
        entries = list(directory.iterdir())
    except OSError:
        return []

    backups: list[dict[str, int | str]] = []
    for entry in entries:
        if not _BACKUP_NAME.fullmatch(entry.name):
            continue
        try:
            info = entry.lstat()
        except OSError:
            continue
        if not stat.S_ISREG(info.st_mode):
            continue
        try:
            created = datetime.strptime(entry.name, "aura-%Y%m%dT%H%M%S%f.db")
        except ValueError:
            continue
        backups.append({
            "name": entry.name,
            "size_bytes": info.st_size,
            "created_at": created.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        })
    return sorted(backups, key=lambda item: str(item["name"]), reverse=True)


def verify_database_backup(database_path: str | Path, name: object) -> dict[str, str | int]:
    """Check one named snapshot read-only, without restoring or exposing its path."""
    if not isinstance(name, str) or not _BACKUP_NAME.fullmatch(name):
        raise ValueError("Invalid backup name")
    directory = _backup_directory(database_path)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("AURA backup directory is unavailable")
    target = directory / name
    try:
        info = target.lstat()
    except OSError as error:
        raise ValueError("AURA backup is unavailable") from error
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("AURA backup is not a regular file")

    connection = None
    descriptor = None
    try:
        # On POSIX, keep the no-follow file descriptor open and have SQLite
        # read that descriptor so a swapped symlink cannot redirect the check.
        if os.name == "posix":
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            directory_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
            try:
                descriptor = os.open(name, flags, dir_fd=directory_fd)
            finally:
                os.close(directory_fd)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("AURA backup is not a regular file")
            connection = sqlite3.connect(f"file:/dev/fd/{descriptor}?mode=ro&immutable=1", uri=True)
        else:
            uri = target.resolve().as_uri() + "?mode=ro&immutable=1"
            connection = sqlite3.connect(uri, uri=True)
        result = connection.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise sqlite3.DatabaseError("SQLite backup failed its integrity check")
    except (OSError, sqlite3.Error) as error:
        raise ValueError("AURA backup failed its integrity check") from error
    finally:
        if connection is not None:
            connection.close()
        if descriptor is not None:
            os.close(descriptor)
    return {
        "name": name,
        "size_bytes": info.st_size,
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "integrity": "ok",
    }


def delete_database_backup(database_path: str | Path, name: object) -> bool:
    """Remove one exact generated snapshot, refusing traversal and symlinks."""
    if not isinstance(name, str) or not _BACKUP_NAME.fullmatch(name):
        raise ValueError("Invalid backup name")
    directory = _backup_directory(database_path)
    try:
        if directory.is_symlink() or not directory.is_dir():
            return False
        if os.name == "posix":
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            directory_fd = os.open(directory, flags)
            try:
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    return False
                os.unlink(name, dir_fd=directory_fd)
            finally:
                os.close(directory_fd)
            return True

        target = directory / name
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode) or target.resolve().parent != directory.resolve():
            return False
        target.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
