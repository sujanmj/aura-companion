from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import pi_node_simulator


TOKEN = "test-enrolled-node-token-which-is-over-32-chars"
SESSION = "room-session-123"
TURN = str(uuid.uuid4())


def response(status: int = 200, body: bytes = b'{"ok": true, "session": {"reserved": true}}') -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value.status = status
    result.__enter__.return_value.read.return_value = body
    return result


class RoomHandoffClientTests(unittest.TestCase):
    def claim(self) -> tuple[int, str]:
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with (
            patch.object(pi_node_simulator, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}),
            redirect_stdout(output),
        ):
            result = pi_node_simulator.claim_invited_room_turn(
                SESSION, 2, TURN, "http://127.0.0.1:8787"
            )
        return result, output.getvalue()

    def test_claim_sends_stable_turn_id_once_with_node_credential(self) -> None:
        with patch("urllib.request.urlopen", return_value=response()) as urlopen:
            result, output = self.claim()

        self.assertEqual(result, 0)
        self.assertIn("AURA_PI_ROOM_CLAIM_OK", output)
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8787/rooms/claim")
        self.assertEqual(request.get_header("X-aura-api-token"), TOKEN)
        self.assertEqual(json.loads(request.data), {
            "session_id": SESSION,
            "generation": 2,
            "turn_id": TURN,
        })

    def test_unknown_network_outcome_is_not_retried(self) -> None:
        with patch(
            "urllib.request.urlopen", side_effect=TimeoutError("response lost")
        ) as urlopen:
            result, output = self.claim()

        self.assertEqual(result, 1)
        self.assertIn("outcome is unknown", output)
        self.assertIn("do not retry with a new turn ID", output)
        urlopen.assert_called_once()

    def test_rejection_is_not_retried_or_exposes_response_body(self) -> None:
        rejected = urllib.error.HTTPError(
            "http://127.0.0.1:8787/rooms/claim",
            409,
            "conflict",
            {},
            io.BytesIO(b"private hub details"),
        )
        with patch("urllib.request.urlopen", side_effect=rejected) as urlopen:
            result, output = self.claim()

        self.assertEqual(result, 1)
        self.assertIn("HTTP 409", output)
        self.assertNotIn("private hub details", output)
        urlopen.assert_called_once()

    def test_invalid_inputs_fail_before_network(self) -> None:
        for session, generation, turn in (
            (SESSION, 0, TURN),
            (SESSION, True, TURN),
            (SESSION, 2, "not-a-uuid"),
            ("", 2, TURN),
        ):
            with self.subTest(generation=generation, turn=turn), patch(
                "urllib.request.urlopen"
            ) as urlopen, patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}):
                self.assertEqual(
                    pi_node_simulator.claim_invited_room_turn(
                        session, generation, turn, "http://127.0.0.1:8787"
                    ),
                    1,
                )
                urlopen.assert_not_called()

    def test_remote_http_is_rejected_before_sending_node_token(self) -> None:
        with (
            patch("urllib.request.urlopen") as urlopen,
            patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}),
        ):
            result = pi_node_simulator.claim_invited_room_turn(
                SESSION, 2, TURN, "http://192.168.1.20:8787"
            )
        self.assertEqual(result, 1)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
