"""Smoke-test a clean extracted preview using only disposable local memory."""
from http.cookiejar import CookieJar
from pathlib import Path
import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

from verify_preview_archive import ROOT, verify_preview_archive


def _safe_environment():
    allowed = {
        "APPDATA", "HOME", "HOMEDRIVE", "HOMEPATH", "LANG", "LOCALAPPDATA",
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "WINDIR",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def _install_dependencies(app_dir: Path, env: dict[str, str]) -> None:
    if os.name == "nt":
        command = ["cmd.exe", "/d", "/s", "/c", "npm ci --ignore-scripts"]
    else:
        command = ["npm", "ci", "--ignore-scripts"]
    result = subprocess.run(
        command, cwd=app_dir, env=env, text=True, capture_output=True,
        timeout=240, check=False,
    )
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-24:])
        raise RuntimeError(f"Clean preview dependency install failed:\n{detail}")


def _unused_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(opener, url: str, *, method: str = "GET", payload=None, origin=None):
    headers = {}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    return opener.open(request, timeout=3)


def _stop_server(process: subprocess.Popen, log) -> None:
    if process.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
        else:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log.close()


def _run_preview_server(
    app_dir: Path, database: Path, temp_root: Path, *, label: str,
) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is unavailable for the clean preview smoke test")
    port = _unused_port()
    origin = f"http://127.0.0.1:{port}"
    token = f"aura-{label}-smoke-token-20261030"
    server_env = {
        **_safe_environment(),
        "AURA_BRAIN_PROVIDER": "local",
        "AURA_DB_PATH": str(database),
        "AURA_ENABLE_ACTIONS": "0",
        "AURA_PORT": str(port),
        "AURA_SESSION_TOKEN": token,
    }
    log = (temp_root / f"{label}-server.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [node, "server/server.mjs"], cwd=app_dir, env=server_env,
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        base = origin + "/"
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError(f"Extracted preview service exited during {label} startup")
            try:
                with _request(opener, base) as response:
                    if response.status != 200 or b"AURA" not in response.read():
                        raise RuntimeError("Extracted preview did not serve its built UI")
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            raise RuntimeError(f"Extracted preview service did not become ready for {label}")

        try:
            _request(opener, origin + "/api/status")
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise RuntimeError("Extracted preview authentication did not fail closed") from error
        else:
            raise RuntimeError("Extracted preview exposed memory before login")

        with _request(
            opener, origin + "/api/login", method="POST",
            payload={"token": token}, origin=origin,
        ) as response:
            if response.status != 200:
                raise RuntimeError("Extracted preview rejected its test session code")
        with _request(opener, origin + "/api/status") as response:
            status = json.loads(response.read())
        if status.get("provider") != "local":
            raise RuntimeError(f"{label} preview did not use the local provider")
        if status.get("actions") is not False:
            raise RuntimeError(f"{label} preview unexpectedly enabled external actions")
        return status
    finally:
        _stop_server(process, log)


def _check_integrity(database: Path, label: str) -> None:
    if not database.is_file():
        raise RuntimeError(f"{label} preview did not create its disposable SQLite database")
    connection = sqlite3.connect(database)
    try:
        integrity = connection.execute("PRAGMA quick_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"{label} preview database failed SQLite integrity check")
    finally:
        connection.close()


def _seed_legacy_database(database: Path) -> None:
    fixture = ROOT / "scripts" / "fixtures" / "legacy_aura_memory.sql"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(fixture.read_text(encoding="utf-8"))
        user_id = connection.execute(
            "INSERT INTO users (name, preferred_name) VALUES (?, ?)",
            ("Sujan M J", "Sujan"),
        ).lastrowid
        connection.execute(
            """INSERT INTO memory_facts (user_id, fact_key, fact_value, confidence)
               VALUES (?, ?, ?, ?)""",
            (user_id, "upgrade_smoke_marker", "legacy-fact-survives", 1.0),
        )
        connection.execute(
            """INSERT INTO conversation_logs (user_id, role, message, emotion_tag)
               VALUES (?, ?, ?, ?)""",
            (user_id, "user", "legacy conversation survives upgrade", None),
        )
        connection.execute(
            """INSERT INTO routine_reminders (user_id, label, local_time)
               VALUES (?, ?, ?)""",
            (user_id, "legacy reminder survives upgrade", "08:15"),
        )
        connection.commit()
    finally:
        connection.close()


def test_clean_preview_install() -> dict[str, object]:
    verification = verify_preview_archive()
    archive = ROOT / "aura-app" / "release" / str(verification["archive"])
    env = _safe_environment()

    with tempfile.TemporaryDirectory(prefix="aura-preview-install-") as directory:
        temp_root = Path(directory)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temp_root)
        app_dir = temp_root / "AURA-Companion" / "aura-app"
        if not (app_dir / "dist" / "index.html").is_file():
            raise RuntimeError("Extracted preview is missing its built application")
        _install_dependencies(app_dir, env)

        database = temp_root / "disposable-memory.sqlite"
        clean_status = _run_preview_server(app_dir, database, temp_root, label="clean")
        if clean_status.get("facts") or clean_status.get("conversations"):
            raise RuntimeError("Clean preview did not start with empty local-only memory")
        _check_integrity(database, "Clean")

        legacy_database = temp_root / "legacy-memory.sqlite"
        _seed_legacy_database(legacy_database)
        legacy_status = _run_preview_server(
            app_dir, legacy_database, temp_root, label="legacy-upgrade",
        )
        facts = legacy_status.get("facts")
        conversations = legacy_status.get("conversations")
        if not isinstance(facts, list) or not any(
            fact.get("fact_key") == "upgrade_smoke_marker"
            and fact.get("fact_value") == "legacy-fact-survives"
            for fact in facts if isinstance(fact, dict)
        ):
            raise RuntimeError("Preview startup did not preserve the legacy memory fact")
        if not isinstance(conversations, list) or not any(
            conversation.get("message") == "legacy conversation survives upgrade"
            for conversation in conversations if isinstance(conversation, dict)
        ):
            raise RuntimeError("Preview startup did not preserve the legacy conversation")
        reminders = legacy_status.get("reminders")
        if not isinstance(reminders, list) or not any(
            reminder.get("label") == "legacy reminder survives upgrade"
            and reminder.get("local_time") == "08:15"
            and reminder.get("days_of_week") == "1,2,3,4,5,6,7"
            and reminder.get("acknowledged_on") is None
            for reminder in reminders if isinstance(reminder, dict)
        ):
            raise RuntimeError("Preview startup did not preserve and migrate the legacy reminder")
        if not legacy_status.get("backups"):
            raise RuntimeError("Legacy memory upgrade did not create its startup backup")
        _check_integrity(legacy_database, "Upgraded legacy")
        backup_name = legacy_status["backups"][0].get("name")
        if not isinstance(backup_name, str) or not re.fullmatch(
            r"aura-\d{8}T\d{12}\.db", backup_name,
        ):
            raise RuntimeError("Legacy startup backup has an unexpected generated name")
        legacy_backup = temp_root / "backups" / backup_name
        _check_integrity(legacy_backup, "Pre-migration backup")
        connection = sqlite3.connect(legacy_backup)
        try:
            saved_fact = connection.execute(
                "SELECT fact_value FROM memory_facts WHERE fact_key=?",
                ("upgrade_smoke_marker",),
            ).fetchone()
            original_reminder = connection.execute(
                "SELECT label, local_time FROM routine_reminders WHERE user_id=1",
            ).fetchone()
            backup_reminder_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(routine_reminders)")
            }
        finally:
            connection.close()
        if not saved_fact or saved_fact[0] != "legacy-fact-survives":
            raise RuntimeError("Startup backup did not retain the pre-migration memory fact")
        if not original_reminder or tuple(original_reminder) != (
            "legacy reminder survives upgrade", "08:15",
        ):
            raise RuntimeError("Startup backup did not retain the pre-migration reminder")
        if {"days_of_week", "acknowledged_on"} & backup_reminder_columns:
            raise RuntimeError("Legacy test fixture already contains the reminder migration fields")
        connection = sqlite3.connect(legacy_database)
        try:
            reminder_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(routine_reminders)")
            }
            event_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(device_events)")
            }
        finally:
            connection.close()
        if not {"days_of_week", "acknowledged_on"}.issubset(reminder_columns):
            raise RuntimeError("Legacy reminder columns were not migrated")
        if "external_event_id" not in event_columns:
            raise RuntimeError("Legacy device-event columns were not migrated")

    return {
        "source_commit": verification["source_commit"],
        "archive_sha256": verification["sha256"],
        "clean_install": "passed",
        "service_start": "passed",
        "unauthenticated_memory": "denied",
        "provider": "local",
        "external_actions": "disabled",
        "database": "temporary_and_integrity_checked",
        "legacy_schema_upgrade": "existing_fact_and_conversation_preserved",
        "legacy_startup_backup": "created_before_migration_and_integrity_checked",
        "legacy_reminder_migration": "schedule_and_acknowledgment_fields",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(test_clean_preview_install(), sort_keys=True))
    except (OSError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile, ValueError) as error:
        raise SystemExit(f"Clean preview install refused: {error}") from None
