from __future__ import annotations

import io
import os
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import pi_node_simulator


TOKEN = "test-node-token-that-is-long-enough-123456"


def response(status: int, body: bytes = b'{"ok": true}') -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value.status = status
    result.__enter__.return_value.read.return_value = body
    return result


class PiNodeHeartbeatTests(unittest.TestCase):
    def call_heartbeat(self) -> tuple[int, str]:
        output = StringIO()
        with (
            patch.object(pi_node_simulator, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}),
            redirect_stdout(output),
        ):
            result = pi_node_simulator.send_node_heartbeat(
                "pi_bedroom_node", "http://127.0.0.1:8787/"
            )
        return result, output.getvalue()

    def test_retries_transient_server_error_with_same_authenticated_request(self) -> None:
        request = urllib.error.HTTPError(
            "http://127.0.0.1:8787/nodes/heartbeat",
            503,
            "unavailable",
            {},
            io.BytesIO(b"ignored"),
        )
        with (
            patch.object(
                pi_node_simulator, "_open_hub_request",
                side_effect=[request, response(200)],
            ) as urlopen,
            patch.object(pi_node_simulator.time, "sleep") as sleep,
        ):
            result, output = self.call_heartbeat()

        self.assertEqual(result, 0)
        self.assertIn("AURA_PI_NODE_HEARTBEAT_OK node_id=pi_bedroom_node", output)
        self.assertEqual(urlopen.call_count, 2)
        first_request = urlopen.call_args_list[0].args[0]
        second_request = urlopen.call_args_list[1].args[0]
        self.assertEqual(first_request.data, second_request.data)
        self.assertEqual(first_request.get_header("X-aura-api-token"), TOKEN)
        self.assertEqual(second_request.get_header("X-aura-api-token"), TOKEN)
        sleep.assert_called_once_with(0.5)

    def test_does_not_retry_revoked_node_credentials(self) -> None:
        unauthorized = urllib.error.HTTPError(
            "http://127.0.0.1:8787/nodes/heartbeat",
            401,
            "unauthorized",
            {},
            io.BytesIO(b"private response body"),
        )
        with (
            patch.object(pi_node_simulator, "_open_hub_request", side_effect=unauthorized) as urlopen,
            patch.object(pi_node_simulator.time, "sleep") as sleep,
        ):
            result, output = self.call_heartbeat()

        self.assertEqual(result, 1)
        self.assertIn("HTTP 401", output)
        self.assertNotIn(TOKEN, output)
        self.assertNotIn("private response body", output)
        urlopen.assert_called_once()
        sleep.assert_not_called()

    def test_retries_request_timeout(self) -> None:
        with (
            patch.object(
                pi_node_simulator, "_open_hub_request",
                side_effect=[TimeoutError("timed out"), response(200)],
            ) as urlopen,
            patch.object(pi_node_simulator.time, "sleep") as sleep,
        ):
            result, output = self.call_heartbeat()

        self.assertEqual(result, 0)
        self.assertIn("AURA_PI_NODE_HEARTBEAT_OK", output)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_invalid_success_body_is_reported_as_rejection(self) -> None:
        with patch.object(pi_node_simulator, "_open_hub_request", return_value=response(200, b"not json")):
            result, output = self.call_heartbeat()

        self.assertEqual(result, 1)
        self.assertIn("hub rejected heartbeat", output)


if __name__ == "__main__":
    unittest.main()
