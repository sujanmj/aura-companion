from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_pi_service_config import validate_environment


class PiServiceConfigTests(unittest.TestCase):
    def test_accepts_strong_token_and_private_database_path(self) -> None:
        self.assertTrue(validate_environment({
            "AURA_SENSOR_API_TOKEN": "random-long-token-1234567890-abcdef",
            "AURA_DB_PATH": "/var/lib/aura/aura_memory.db",
        }))

    def test_rejects_missing_short_or_trivial_tokens(self) -> None:
        for token in ("", "too-short", "x" * 40, " token-with-spaces-1234567890123456789"):
            with self.subTest(token_length=len(token)):
                self.assertFalse(validate_environment({
                    "AURA_SENSOR_API_TOKEN": token,
                    "AURA_DB_PATH": "/var/lib/aura/aura_memory.db",
                }))

    def test_rejects_database_path_outside_service_state(self) -> None:
        self.assertFalse(validate_environment({
            "AURA_SENSOR_API_TOKEN": "random-long-token-1234567890-abcdef",
            "AURA_DB_PATH": "/tmp/aura_memory.db",
        }))

    def test_systemd_hub_is_non_root_hardened_and_checks_token_before_start(self) -> None:
        unit = (ROOT / "deploy/systemd/aura-sensor-api.service").read_text()
        self.assertIn("User=aura", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ProtectHome=true", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("AURA_DB_PATH=/var/lib/aura/aura_memory.db", unit)
        self.assertLess(unit.index("ExecStartPre="), unit.index("ExecStart="))


if __name__ == "__main__":
    unittest.main()
