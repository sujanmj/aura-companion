"""Smoke-test a clean extracted preview using only disposable local memory."""
from http.cookiejar import CookieJar
from pathlib import Path
import json
import os
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
        command = ["cmd.exe", "/d", "/s", "/c", "npm ci --ignore-scripts --offline"]
    else:
        command = ["npm", "ci", "--ignore-scripts", "--offline"]
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


def test_clean_preview_install() -> dict[str, object]:
    verification = verify_preview_archive()
    archive = ROOT / "aura-app" / "release" / str(verification["archive"])
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is unavailable for the clean preview smoke test")
    env = _safe_environment()
    token = "aura-clean-preview-smoke-token-20261030"

    with tempfile.TemporaryDirectory(prefix="aura-preview-install-") as directory:
        temp_root = Path(directory)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temp_root)
        app_dir = temp_root / "AURA-Companion" / "aura-app"
        if not (app_dir / "dist" / "index.html").is_file():
            raise RuntimeError("Extracted preview is missing its built application")
        _install_dependencies(app_dir, env)

        database = temp_root / "disposable-memory.sqlite"
        port = _unused_port()
        origin = f"http://127.0.0.1:{port}"
        server_env = {
            **env,
            "AURA_BRAIN_PROVIDER": "local",
            "AURA_DB_PATH": str(database),
            "AURA_ENABLE_ACTIONS": "0",
            "AURA_PORT": str(port),
            "AURA_SESSION_TOKEN": token,
        }
        log = (temp_root / "server.log").open("w", encoding="utf-8")
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
                    raise RuntimeError("Extracted preview service exited during startup")
                try:
                    with _request(opener, base) as response:
                        if response.status != 200 or b"AURA" not in response.read():
                            raise RuntimeError("Extracted preview did not serve its built UI")
                    break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("Extracted preview service did not become ready")

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
            if status.get("provider") != "local" or status.get("facts") or status.get("conversations"):
                raise RuntimeError("Clean preview did not start with empty local-only memory")
            if status.get("actions") is not False:
                raise RuntimeError("Clean preview unexpectedly enabled external actions")
        finally:
            _stop_server(process, log)

        if not database.is_file():
            raise RuntimeError("Clean preview did not create its disposable SQLite database")
        connection = sqlite3.connect(database)
        try:
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RuntimeError("Clean preview database failed SQLite integrity check")
        finally:
            connection.close()

    return {
        "source_commit": verification["source_commit"],
        "archive_sha256": verification["sha256"],
        "clean_install": "passed",
        "service_start": "passed",
        "unauthenticated_memory": "denied",
        "provider": "local",
        "external_actions": "disabled",
        "database": "temporary_and_integrity_checked",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(test_clean_preview_install(), sort_keys=True))
    except (OSError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile, ValueError) as error:
        raise SystemExit(f"Clean preview install refused: {error}") from None
