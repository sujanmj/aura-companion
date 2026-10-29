from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import enroll_sensor_node, show_dashboard_status


ADMIN_TOKEN = "sensor-admin-token-long-enough-for-tests-123"


def response(status: int, body: dict) -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value.status = status
    result.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
    return result


class SensorAdminClientTests(unittest.TestCase):
    def test_enrollment_uses_authenticated_safe_hub_request(self) -> None:
        with (
            patch.object(enroll_sensor_node, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                enroll_sensor_node,
                "open_sensor_api_request",
                return_value=response(201, {
                    "token": "new-node-token-which-is-secret",
                    "node": {"node_id": "bedroom"},
                }),
            ) as open_request,
            patch.object(sys, "argv", ["enroll_sensor_node.py", "bedroom", "Bedroom"]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(enroll_sensor_node.main(), 0)

        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8787/nodes/enroll")
        self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 10})

    def test_enrollment_refuses_remote_http_before_sending_admin_token(self) -> None:
        with (
            patch.object(enroll_sensor_node, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(enroll_sensor_node, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", [
                "enroll_sensor_node.py", "bedroom", "Bedroom", "--hub-url",
                "http://192.168.1.20:8787",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(enroll_sensor_node.main(), 1)
        open_request.assert_not_called()

    def test_dashboard_status_uses_authenticated_safe_hub_request(self) -> None:
        with (
            patch.object(show_dashboard_status, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                show_dashboard_status,
                "open_sensor_api_request",
                return_value=response(200, {"summary": {}}),
            ) as open_request,
            patch.object(sys, "argv", ["show_dashboard_status.py"]),
            redirect_stdout(io.StringIO()),
        ):
            show_dashboard_status.main()

        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8787/dashboard/status")
        self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 15})

    def test_dashboard_status_refuses_remote_http_before_sending_admin_token(self) -> None:
        with (
            patch.object(show_dashboard_status, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(show_dashboard_status, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", [
                "show_dashboard_status.py", "http://192.168.1.20:8787",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            show_dashboard_status.main()
        open_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
