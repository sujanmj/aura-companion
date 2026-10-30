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

from scripts import (
    enroll_sensor_node,
    list_sensor_nodes,
    revoke_sensor_node,
    show_dashboard_status,
    test_confirmation_api,
    test_dashboard_api,
    test_incident_api,
    test_sensor_api_auth,
    test_sensor_api_client,
    test_sensor_api_event_status,
    test_runtime_dashboard_heartbeat,
)


ADMIN_TOKEN = "sensor-admin-token-long-enough-for-tests-123"


def response(status: int, body: dict) -> MagicMock:
    result = MagicMock()
    result.__enter__.return_value.status = status
    result.__enter__.return_value.read.return_value = json.dumps(body).encode("utf-8")
    return result


class SensorAdminClientTests(unittest.TestCase):
    def test_node_status_lists_only_safe_fields_over_authenticated_transport(self) -> None:
        with (
            patch.object(list_sensor_nodes, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                list_sensor_nodes,
                "open_sensor_api_request",
                return_value=response(200, {
                    "ok": True,
                    "nodes": [{
                        "node_id": "bedroom",
                        "display_name": "Bedroom Pi",
                        "room": "bedroom",
                        "online": 1,
                        "last_seen_at": "2026-10-30 07:00:00",
                        "token": "must-not-be-printed",
                    }],
                }),
            ) as open_request,
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(list_sensor_nodes.main(), 0)

        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8787/nodes/status")
        self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 10})
        self.assertIn("bedroom | Bedroom Pi | room=bedroom | online", output.getvalue())
        self.assertIn("does not confirm sensor or playback operation", output.getvalue())
        self.assertNotIn("must-not-be-printed", output.getvalue())

    def test_node_status_rejects_unsafe_remote_http_before_sending_credentials(self) -> None:
        with (
            patch.object(list_sensor_nodes, "load_env_file"),
            patch.dict(os.environ, {
                "AURA_SENSOR_API_TOKEN": ADMIN_TOKEN,
                "AURA_SENSOR_API_URL": "http://192.168.1.20:8787",
            }, clear=True),
            patch.object(list_sensor_nodes, "open_sensor_api_request") as open_request,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(list_sensor_nodes.main(), 1)
        open_request.assert_not_called()

    def test_node_status_rejects_terminal_control_characters_and_bad_records(self) -> None:
        invalid_nodes = [
            [{
                "node_id": "bedroom",
                "display_name": "Bedroom" + chr(10) + "FORGED",
                "room": "bedroom",
                "online": 1,
            }],
            [{"node_id": "bad node", "display_name": "Bedroom", "room": "bedroom", "online": 1}],
            [{"node_id": "bedroom", "display_name": "Bedroom", "room": "bedroom", "online": 2}],
            [{"node_id": "bedroom", "display_name": "Bedroom", "room": "bedroom", "online": 1}],
        ]
        for nodes in invalid_nodes:
            with (
                self.subTest(nodes=nodes),
                patch.object(list_sensor_nodes, "load_env_file"),
                patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
                patch.object(
                    list_sensor_nodes,
                    "open_sensor_api_request",
                    return_value=response(200, {"ok": True, "nodes": nodes}),
                ),
                redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(list_sensor_nodes.main(), 1)
                self.assertNotIn("Bedroom" + chr(10) + "FORGED", output.getvalue())

    def test_node_revocation_requires_typed_confirmation_and_uses_safe_admin_transport(
        self,
    ) -> None:
        with (
            patch.object(revoke_sensor_node, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch("builtins.input", return_value="REVOKE bedroom"),
            patch.object(
                revoke_sensor_node,
                "open_sensor_api_request",
                return_value=response(200, {"ok": True, "revoked": True}),
            ) as open_request,
            patch.object(sys, "argv", ["revoke_sensor_node.py", "bedroom"]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(revoke_sensor_node.main(), 0)

        request = open_request.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8787/nodes/revoke")
        self.assertEqual(json.loads(request.data), {"node_id": "bedroom"})
        self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 10})

    def test_node_revocation_cancellation_and_invalid_ids_do_not_send_requests(self) -> None:
        with (
            patch.object(revoke_sensor_node, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch("builtins.input", return_value=""),
            patch.object(revoke_sensor_node, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", ["revoke_sensor_node.py", "bedroom"]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(revoke_sensor_node.main(), 1)
        open_request.assert_not_called()

        with (
            patch("builtins.input") as input_prompt,
            patch.object(revoke_sensor_node, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", ["revoke_sensor_node.py", "bad node"]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(revoke_sensor_node.main(), 1)
        input_prompt.assert_not_called()
        open_request.assert_not_called()

    def test_node_revocation_refuses_remote_http_before_sending_admin_token(self) -> None:
        with (
            patch.object(revoke_sensor_node, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch("builtins.input", return_value="REVOKE bedroom"),
            patch.object(revoke_sensor_node, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", [
                "revoke_sensor_node.py", "bedroom", "--hub-url", "http://192.168.1.20:8787",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(revoke_sensor_node.main(), 1)
        open_request.assert_not_called()

    def test_node_revocation_requires_explicit_success_response(self) -> None:
        with (
            patch.object(revoke_sensor_node, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch("builtins.input", return_value="REVOKE bedroom"),
            patch.object(
                revoke_sensor_node,
                "open_sensor_api_request",
                return_value=response(200, {"ok": True, "revoked": False}),
            ),
            patch.object(sys, "argv", ["revoke_sensor_node.py", "bedroom"]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(revoke_sensor_node.main(), 1)

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

    def test_sensor_api_example_client_uses_direct_authenticated_transport(self) -> None:
        responses = [
            response(200, {"ok": True}),
            response(201, {"ok": True, "id": 7}),
            response(200, {"ok": True, "events": []}),
        ]
        with (
            patch.object(test_sensor_api_client, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                test_sensor_api_client,
                "open_sensor_api_request",
                side_effect=responses,
            ) as open_request,
            patch.object(sys, "argv", [
                "test_sensor_api_client.py", "http://127.0.0.1:8787/",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            test_sensor_api_client.main()

        requests = [call.args[0] for call in open_request.call_args_list]
        self.assertEqual([request.full_url for request in requests], [
            "http://127.0.0.1:8787/health",
            "http://127.0.0.1:8787/events",
            "http://127.0.0.1:8787/events/latest",
        ])
        self.assertEqual(open_request.call_count, 3)
        for request in requests[1:]:
            self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)

    def test_sensor_api_example_client_refuses_remote_http_before_request(self) -> None:
        with (
            patch.object(test_sensor_api_client, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(test_sensor_api_client, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", [
                "test_sensor_api_client.py", "http://192.168.1.20:8787",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as raised:
                test_sensor_api_client.main()
        self.assertEqual(raised.exception.code, 1)
        open_request.assert_not_called()

    def test_sensor_api_auth_client_uses_direct_transport_for_admin_token(self) -> None:
        responses = [
            response(200, {"ok": True}),
            response(401, {"error": "unauthorized"}),
            response(401, {"error": "unauthorized"}),
            response(200, {"ok": True}),
        ]
        with (
            patch.object(test_sensor_api_auth, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                test_sensor_api_auth,
                "open_sensor_api_request",
                side_effect=responses,
            ) as open_request,
            patch.object(sys, "argv", ["test_sensor_api_auth.py"]),
            redirect_stdout(io.StringIO()),
        ):
            test_sensor_api_auth.main()

        requests = [call.args[0] for call in open_request.call_args_list]
        self.assertEqual(len(requests), 4)
        self.assertTrue(requests[-1].full_url.endswith("/events"))
        self.assertEqual(requests[-1].get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(requests[1].get_header("X-aura-api-token"), None)

    def test_sensor_api_auth_client_refuses_remote_http_before_request(self) -> None:
        with (
            patch.object(test_sensor_api_auth, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(test_sensor_api_auth, "open_sensor_api_request") as open_request,
            patch.object(sys, "argv", [
                "test_sensor_api_auth.py", "http://192.168.1.20:8787",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as raised:
                test_sensor_api_auth.main()
        self.assertEqual(raised.exception.code, 1)
        open_request.assert_not_called()

    def test_sensor_event_status_client_uses_direct_authenticated_transport(self) -> None:
        responses = [
            response(200, {"ok": True}),
            response(200, {"ok": True, "event": {"event_id": 7}}),
            response(200, {"ok": True, "events": [{"id": 7, "action_status": "dispatched"}]}),
        ]
        with (
            patch.object(test_sensor_api_event_status, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                test_sensor_api_event_status,
                "open_sensor_api_request",
                side_effect=responses,
            ) as open_request,
            patch.object(sys, "argv", ["test_sensor_api_event_status.py"]),
            redirect_stdout(io.StringIO()),
        ):
            test_sensor_api_event_status.main()

        requests = [call.args[0] for call in open_request.call_args_list]
        self.assertEqual(open_request.call_count, 3)
        self.assertEqual(requests[1].get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(requests[2].get_header("X-aura-api-token"), ADMIN_TOKEN)

    def test_sensor_event_status_client_refuses_remote_http_before_request(self) -> None:
        with (
            patch.object(test_sensor_api_event_status, "load_env_file"),
            patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
            patch.object(
                test_sensor_api_event_status,
                "open_sensor_api_request",
            ) as open_request,
            patch.object(sys, "argv", [
                "test_sensor_api_event_status.py", "http://192.168.1.20:8787",
            ]),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as raised:
                test_sensor_api_event_status.main()
        self.assertEqual(raised.exception.code, 1)
        open_request.assert_not_called()

    def test_incident_confirmation_dashboard_and_heartbeat_use_direct_transport(self) -> None:
        cases = (
            (test_incident_api, "test_incident_api.py", "GET", "/incidents/recent", 15),
            (test_confirmation_api, "test_confirmation_api.py", "GET", "/confirmations/pending", 15),
            (test_dashboard_api, "test_dashboard_api.py", "GET", "/dashboard/status", 15),
        )
        for module, label, method, path, timeout in cases:
            with self.subTest(client=label):
                opener = patch.object(
                    module,
                    "open_sensor_api_request",
                    return_value=response(200, {"ok": True}),
                )
                with opener as open_request:
                    module._request(
                        method,
                        f"https://hub.example{path}",
                        token=ADMIN_TOKEN,
                    )
                request = open_request.call_args.args[0]
                self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)
                self.assertEqual(open_request.call_args.kwargs, {"timeout": timeout})

        with patch.object(
            test_runtime_dashboard_heartbeat,
            "open_sensor_api_request",
            return_value=response(200, {}),
        ) as open_request:
            self.assertEqual(
                test_runtime_dashboard_heartbeat._request(
                    "https://hub.example/dashboard/status", ADMIN_TOKEN, timeout=9,
                ),
                200,
            )
        request = open_request.call_args.args[0]
        self.assertEqual(request.get_header("X-aura-api-token"), ADMIN_TOKEN)
        self.assertEqual(open_request.call_args.kwargs, {"timeout": 9})

    def test_remaining_sensor_api_probes_refuse_remote_http_before_request(self) -> None:
        clients = (
            (test_incident_api, "test_incident_api.py"),
            (test_confirmation_api, "test_confirmation_api.py"),
            (test_dashboard_api, "test_dashboard_api.py"),
            (test_runtime_dashboard_heartbeat, "test_runtime_dashboard_heartbeat.py"),
        )
        for module, label in clients:
            with self.subTest(client=label):
                with (
                    patch.object(module, "load_env_file"),
                    patch.dict(os.environ, {"AURA_SENSOR_API_TOKEN": ADMIN_TOKEN}, clear=True),
                    patch.object(module, "open_sensor_api_request") as open_request,
                    patch.object(sys, "argv", [label, "http://192.168.1.20:8787"]),
                    redirect_stdout(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit) as raised:
                        module.main()
                self.assertEqual(raised.exception.code, 1)
                open_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
