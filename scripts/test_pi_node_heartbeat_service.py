from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_pi_node_heartbeat_config import validate_environment
from scripts.run_pi_node_heartbeat import run_heartbeat_loop


def valid_environment() -> dict[str, str]:
    return {
        "AURA_SENSOR_NODE_TOKEN": "random-node-token-1234567890-abcdef",
        "AURA_SENSOR_NODE_ID": "pi_bedroom_node",
        "AURA_SENSOR_API_URL": "https://aura-hub.local:8787",
        "AURA_SENSOR_NODE_HEARTBEAT_INTERVAL_SECONDS": "30",
    }


class StopAfterWait:
    def __init__(self) -> None:
        self.stopped = False
        self.waits: list[int] = []

    def is_set(self) -> bool:
        return self.stopped

    def wait(self, timeout: int) -> bool:
        self.waits.append(timeout)
        self.stopped = True
        return True


class PiNodeHeartbeatServiceTests(unittest.TestCase):
    def test_accepts_enrolled_node_configuration(self) -> None:
        self.assertTrue(validate_environment(valid_environment()))

    def test_rejects_missing_credentials_or_invalid_node_identity(self) -> None:
        for key, value in (
            ("AURA_SENSOR_NODE_TOKEN", ""),
            ("AURA_SENSOR_NODE_TOKEN", "x" * 40),
            ("AURA_SENSOR_NODE_TOKEN", " token-with-padding-12345678901234567890"),
            ("AURA_SENSOR_NODE_ID", "../other-node"),
            ("AURA_SENSOR_NODE_ID", "x" * 65),
        ):
            environment = valid_environment()
            environment[key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(validate_environment(environment))

    def test_rejects_untrusted_or_malformed_hub_url(self) -> None:
        for url in (
            "",
            "file:///tmp/aura",
            "https://user:password@example.test",
            "http://example.test/api",
            "http://example.test/?token=secret",
            "http://example.test/#fragment",
        ):
            environment = valid_environment()
            environment["AURA_SENSOR_API_URL"] = url
            with self.subTest(url=url):
                self.assertFalse(validate_environment(environment))

    def test_allows_loopback_http_for_local_development(self) -> None:
        environment = valid_environment()
        environment["AURA_SENSOR_API_URL"] = "http://127.0.0.1:8787"
        self.assertTrue(validate_environment(environment))

    def test_requires_a_heartbeat_interval_within_online_window(self) -> None:
        for interval in ("invalid", "4", "61"):
            environment = valid_environment()
            environment["AURA_SENSOR_NODE_HEARTBEAT_INTERVAL_SECONDS"] = interval
            with self.subTest(interval=interval):
                self.assertFalse(validate_environment(environment))

    def test_loop_sends_immediately_then_waits_and_stops_cleanly(self) -> None:
        stop = StopAfterWait()
        heartbeat = Mock(return_value=1)

        run_heartbeat_loop("pi_bedroom_node", 30, stop, heartbeat)

        heartbeat.assert_called_once_with("pi_bedroom_node")
        self.assertEqual(stop.waits, [30])

    def test_systemd_service_is_hardened_and_fails_closed(self) -> None:
        unit = (ROOT / "deploy/systemd/aura-pi-node-heartbeat.service").read_text()
        self.assertIn("User=aura-node", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ProtectHome=true", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("MemoryDenyWriteExecute=true", unit)
        self.assertIn("EnvironmentFile=/etc/aura/aura-node.env", unit)
        self.assertLess(unit.index("ExecStartPre="), unit.index("ExecStart="))


if __name__ == "__main__":
    unittest.main()
