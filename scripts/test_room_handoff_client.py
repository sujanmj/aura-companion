from __future__ import annotations

import io
import json
import time
import os
import sys
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import sensor_transport
from scripts import pi_node_simulator


TOKEN = "test-enrolled-node-token-which-is-over-32-chars"
SESSION = "room-session-123"
TURN = str(uuid.uuid4())


def response(status: int = 200, body: bytes | None = None) -> MagicMock:
    if body is None:
        body = json.dumps({
            "ok": True,
            "session": {
                "reserved": True,
                "session_id": SESSION,
                "generation": 2,
                "turn_id": TURN,
                "expires_at": time.time() + 60,
            },
        }).encode("utf-8")
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
        with patch.object(pi_node_simulator, "_open_hub_request", return_value=response()) as urlopen:
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
        with patch.object(
            pi_node_simulator, "_open_hub_request", side_effect=TimeoutError("response lost")
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
        with patch.object(pi_node_simulator, "_open_hub_request", side_effect=rejected) as urlopen:
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
            with self.subTest(generation=generation, turn=turn), patch.object(
                pi_node_simulator, "_open_hub_request"
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
            patch.object(pi_node_simulator, "_open_hub_request") as urlopen,
            patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}),
        ):
            result = pi_node_simulator.claim_invited_room_turn(
                SESSION, 2, TURN, "http://192.168.1.20:8787"
            )
        self.assertEqual(result, 1)
        urlopen.assert_not_called()

    def test_hub_opener_ignores_proxies_and_refuses_redirects(self) -> None:
        opener = MagicMock()
        request = urllib.request.Request("https://hub.example/rooms/claim")
        with patch.object(urllib.request, "build_opener", return_value=opener) as build:
            pi_node_simulator._open_hub_request(request, timeout=7)

        self.assertEqual(opener.open.call_args.args[0], request)
        self.assertEqual(opener.open.call_args.kwargs, {"timeout": 7})
        proxy_handler, redirect_handler = build.call_args.args
        self.assertIsInstance(proxy_handler, urllib.request.ProxyHandler)
        self.assertEqual(proxy_handler.proxies, {})
        self.assertIsInstance(redirect_handler, sensor_transport._NoRedirectHandler)
        self.assertIsNone(redirect_handler.redirect_request(
            request, None, 302, "Found", {}, "https://attacker.example/"
        ))

    def test_mismatched_or_stale_claim_response_fails_closed(self) -> None:
        valid_session = {
            "reserved": True,
            "session_id": SESSION,
            "generation": 2,
            "turn_id": TURN,
            "expires_at": time.time() + 60,
        }
        invalid_sessions = (
            {**valid_session, "session_id": "different-session"},
            {**valid_session, "generation": 3},
            {**valid_session, "turn_id": str(uuid.uuid4())},
            {**valid_session, "expires_at": time.time() - 1},
            {**valid_session, "expires_at": float("inf")},
            {**valid_session, "expires_at": float("nan")},
            {**valid_session, "expires_at": True},
            {key: value for key, value in valid_session.items() if key != "turn_id"},
        )
        for invalid in invalid_sessions:
            with self.subTest(session=invalid), patch.object(
                pi_node_simulator, "_open_hub_request",
                return_value=response(body=json.dumps({"ok": True, "session": invalid}).encode()),
            ) as urlopen:
                result, output = self.claim()
            self.assertEqual(result, 1)
            self.assertIn("do not play this reply", output)
            urlopen.assert_called_once()

    def test_claim_response_must_be_explicitly_successful(self) -> None:
        valid = {
            "session": {
                "reserved": True,
                "session_id": SESSION,
                "generation": 2,
                "turn_id": TURN,
                "expires_at": time.time() + 60,
            },
        }
        with patch.object(
            pi_node_simulator, "_open_hub_request",
            return_value=response(body=json.dumps({**valid, "ok": False}).encode()),
        ) as urlopen:
            result, output = self.claim()
        self.assertEqual(result, 1)
        self.assertIn("do not play this reply", output)
        urlopen.assert_called_once()

    def test_live_claim_validation_is_a_single_point_in_time_check(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with (
            patch.object(pi_node_simulator, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}),
            patch.object(pi_node_simulator, "_open_hub_request", return_value=response()) as urlopen,
            redirect_stdout(output),
        ):
            result = pi_node_simulator.validate_invited_room_turn(
                SESSION, 2, TURN, "http://127.0.0.1:8787"
            )

        self.assertEqual(result, 0)
        self.assertIn("VALID_AT_CHECK", output.getvalue())
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8787/rooms/claim/validate")
        self.assertEqual(request.get_header("X-aura-api-token"), TOKEN)
        self.assertEqual(json.loads(request.data), {
            "session_id": SESSION,
            "generation": 2,
            "turn_id": TURN,
        })

    def test_unknown_or_stale_validation_never_suggests_playback(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO

        failures = (
            {"side_effect": TimeoutError("unknown")},
            {"return_value": response(body=json.dumps({"ok": False}).encode())},
        )
        for failure in failures:
            output = StringIO()
            with (
                patch.object(pi_node_simulator, "load_env_file"),
                patch.dict(os.environ, {"AURA_SENSOR_NODE_TOKEN": TOKEN}),
                patch.object(pi_node_simulator, "_open_hub_request", **failure) as urlopen,
                redirect_stdout(output),
            ):
                result = pi_node_simulator.validate_invited_room_turn(
                    SESSION, 2, TURN, "http://127.0.0.1:8787"
                )
            self.assertEqual(result, 1)
            self.assertIn("do not play this reply", output.getvalue())
            urlopen.assert_called_once()

    def test_cli_exposes_validation_without_claiming_or_playing(self) -> None:
        with patch.object(pi_node_simulator, "validate_invited_room_turn", return_value=0) as validate:
            result = pi_node_simulator.main([
                "--validate-session", SESSION,
                "--generation", "2",
                "--turn-id", TURN,
                "--hub-url", "http://127.0.0.1:8787",
            ])
        self.assertEqual(result, 0)
        validate.assert_called_once_with(
            SESSION, 2, TURN, hub_url="http://127.0.0.1:8787"
        )

    def test_cli_rejects_claim_and_validation_combined(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with redirect_stdout(output):
            result = pi_node_simulator.main([
                "--claim-session", SESSION,
                "--validate-session", SESSION,
                "--generation", "2",
                "--turn-id", TURN,
            ])
        self.assertEqual(result, 1)
        self.assertIn("Choose either", output.getvalue())


if __name__ == "__main__":
    unittest.main()
