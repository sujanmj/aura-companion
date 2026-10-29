from __future__ import annotations

import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import sensor_transport
from scripts import room_invitation


TOKEN = "test-owner-admin-token-that-is-long-enough-for-aura"
SESSION = "5d62dff8-07bb-4a96-b19c-0f7046133798"
HUB = "http://127.0.0.1:8787"


def response(body: dict | None = None, status: int = 200) -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value.status = status
    result.__enter__.return_value.read.return_value = json.dumps(
        body or {
            "ok": True,
            "session": {
                "session_id": SESSION,
                "generation": 1,
                "node_id": "bedroom",
                "expires_at": 1_900_000_000,
            },
        }
    ).encode()
    return result


class RoomInvitationTests(unittest.TestCase):
    def invoke(self, args: list[str], answer: str | None = None) -> tuple[int, str]:
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with (
            patch.object(room_invitation, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": TOKEN}, clear=True),
            patch("builtins.input", return_value=answer or ""),
            redirect_stdout(output),
        ):
            result = room_invitation.main(["--hub-url", HUB, *args])
        return result, output.getvalue()

    def test_start_requires_exact_typed_consent_and_sends_admin_request(self) -> None:
        with patch("urllib.request.build_opener") as build_opener:
            result, output = self.invoke(["start", "bedroom"], "invite bedroom")
        self.assertEqual(result, 1)
        self.assertIn("CANCELLED", output)
        build_opener.assert_not_called()

        with patch("urllib.request.build_opener") as build_opener:
            build_opener.return_value.open.return_value = response()
            result, output = self.invoke(["start", "bedroom"], "INVITE bedroom")
        self.assertEqual(result, 0)
        self.assertIn(f"session_id={SESSION}", output)
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(build_opener.call_args.args[0].proxies, {})
        self.assertIsInstance(build_opener.call_args.args[1], sensor_transport._NoRedirectHandler)
        self.assertEqual(request.full_url, f"{HUB}/rooms/start")
        self.assertEqual(request.get_header("X-aura-api-token"), TOKEN)
        self.assertEqual(json.loads(request.data), {"node_id": "bedroom", "approved": True})

    def test_transfer_and_stop_require_action_specific_confirmation(self) -> None:
        with patch("urllib.request.build_opener") as build_opener:
            build_opener.return_value.open.return_value = response()
            result, _ = self.invoke(
                ["transfer", SESSION, "1", "kitchen"], "TRANSFER kitchen"
            )
        self.assertEqual(result, 0)
        transfer = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(transfer.full_url, f"{HUB}/rooms/transfer")
        self.assertEqual(json.loads(transfer.data), {
            "session_id": SESSION,
            "generation": 1,
            "node_id": "kitchen",
            "approved": True,
        })

        with patch("urllib.request.build_opener") as build_opener:
            build_opener.return_value.open.return_value = response({"ok": True, "session": None})
            result, output = self.invoke(["stop", SESSION, "2"], f"STOP {SESSION}")
        self.assertEqual(result, 0)
        self.assertIn("STOPPED", output)
        stop = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(stop.full_url, f"{HUB}/rooms/stop")
        self.assertEqual(json.loads(stop.data), {"session_id": SESSION, "generation": 2})

    def test_status_is_read_only_and_prints_only_safe_session_fields(self) -> None:
        body = {"ok": True, "session": {
            "session_id": SESSION,
            "generation": 3,
            "node_id": "bedroom",
            "expires_at": 1_900_000_000,
            "user_id": 77,
            "token": "must-not-print",
        }}
        with patch("urllib.request.build_opener") as build_opener:
            build_opener.return_value.open.return_value = response(body)
            result, output = self.invoke(["status"])
        self.assertEqual(result, 0)
        self.assertEqual(build_opener.return_value.open.call_args.args[0].full_url, f"{HUB}/rooms/status")
        self.assertIn("generation=3", output)
        self.assertNotIn("user_id", output)
        self.assertNotIn("must-not-print", output)

    def test_missing_token_and_remote_http_fail_before_network_or_consent(self) -> None:
        with (
            patch.object(room_invitation, "load_env_file"),
            patch.dict(os.environ, {}, clear=True),
            patch("builtins.input") as prompt,
            patch("urllib.request.build_opener") as build_opener,
        ):
            result = room_invitation.main(["start", "bedroom"])
        self.assertEqual(result, 1)
        prompt.assert_not_called()
        build_opener.assert_not_called()

        with patch("urllib.request.build_opener") as build_opener:
            output = io.StringIO()
            with (
                patch.object(room_invitation, "load_env_file"),
                patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": TOKEN}, clear=True),
                patch("builtins.input", return_value="INVITE bedroom"),
                patch("sys.stdout", output),
            ):
                result = room_invitation.main([
                    "--hub-url", "http://192.168.1.20:8787", "start", "bedroom"
                ])
        self.assertEqual(result, 1)
        build_opener.assert_not_called()

    def test_http_and_unknown_network_results_are_safe_and_never_retried(self) -> None:
        rejected = urllib.error.HTTPError(
            f"{HUB}/rooms/start", 409, "conflict", {}, io.BytesIO(b"private hub detail")
        )
        for error in (rejected, TimeoutError("private network detail")):
            with patch("urllib.request.build_opener") as build_opener:
                build_opener.return_value.open.side_effect = error
                result, output = self.invoke(["status"])
            self.assertEqual(result, 1)
            build_opener.return_value.open.assert_called_once()
            self.assertNotIn("private hub detail", output)
            self.assertNotIn("private network detail", output)
            if isinstance(error, urllib.error.HTTPError):
                self.assertIn("HTTP 409", output)
            else:
                self.assertIn("check invitation status before trying again", output)

    def test_redirect_handler_never_forwards_the_admin_token(self) -> None:
        handler = sensor_transport._NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(
            None, None, 307, "Temporary Redirect", {}, "https://other.example/rooms/status"
        ))


if __name__ == "__main__":
    unittest.main()
