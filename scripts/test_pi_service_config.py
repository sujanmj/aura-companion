from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_pi_service_config import validate_environment


class PiServiceConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name).resolve()
        self.cert = folder / "server.crt"
        self.key = folder / "server.key"
        self.cert.write_text("test certificate placeholder")
        self.key.write_text("test private key placeholder")
        self.key.chmod(0o640)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def valid_environment(self) -> dict[str, str]:
        return {
            "AURA_SENSOR_API_TOKEN": "random-long-token-1234567890-abcdef",
            "AURA_DB_PATH": "/var/lib/aura/aura_memory.db",
            "AURA_SENSOR_TLS_CERT_FILE": str(self.cert),
            "AURA_SENSOR_TLS_KEY_FILE": str(self.key),
        }

    def test_accepts_strong_token_and_private_database_path(self) -> None:
        self.assertTrue(validate_environment(self.valid_environment()))

    def test_rejects_missing_short_or_trivial_tokens(self) -> None:
        for token in ("", "too-short", "x" * 40, " token-with-spaces-1234567890123456789"):
            with self.subTest(token_length=len(token)):
                environment = self.valid_environment()
                environment["AURA_SENSOR_API_TOKEN"] = token
                self.assertFalse(validate_environment(environment))

    def test_rejects_database_path_outside_service_state(self) -> None:
        environment = self.valid_environment()
        environment["AURA_DB_PATH"] = "/tmp/aura_memory.db"
        self.assertFalse(validate_environment(environment))

    def test_requires_existing_tls_files_and_private_key_permissions(self) -> None:
        environment = self.valid_environment()
        environment.pop("AURA_SENSOR_TLS_CERT_FILE")
        self.assertFalse(validate_environment(environment))
        self.key.chmod(0o644)
        self.assertFalse(validate_environment(self.valid_environment()))

    def test_rejects_certificate_files_reached_through_symlinked_directory(self) -> None:
        if sys.platform == "win32":
            self.skipTest("symlink creation is not portable on Windows")
        root = Path(self.temp.name).resolve()
        target = root / "actual"
        target.mkdir()
        cert = target / "server.crt"
        cert.write_text("test certificate placeholder")
        alias = root / "alias"
        alias.symlink_to(target, target_is_directory=True)
        environment = self.valid_environment()
        environment["AURA_SENSOR_TLS_CERT_FILE"] = str(alias / cert.name)
        self.assertFalse(validate_environment(environment))

    def test_systemd_hub_is_non_root_hardened_and_checks_token_before_start(self) -> None:
        unit = (ROOT / "deploy/systemd/aura-sensor-api.service").read_text()
        self.assertIn("User=aura", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ProtectHome=true", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("AURA_DB_PATH=/var/lib/aura/aura_memory.db", unit)
        self.assertIn("AURA_SENSOR_TLS_CERT_FILE=/etc/aura/tls/server.crt", unit)
        self.assertIn("AURA_SENSOR_TLS_KEY_FILE=/etc/aura/tls/server.key", unit)
        self.assertLess(unit.index("ExecStartPre="), unit.index("ExecStart="))


if __name__ == "__main__":
    unittest.main()
