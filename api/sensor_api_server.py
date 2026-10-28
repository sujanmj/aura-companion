from __future__ import annotations

import json
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from actions.action_dispatcher import ActionDispatcher
from actions.voice_runtime import create_runtime_speaker
from api.dashboard_service import DashboardService
from config.env_loader import load_env_file
from devices.event_bus import DeviceEventBus
from devices.room_handoff import RoomHandoff, HandoffDenied
from memory.sqlite_store import AuraMemoryStore, DEFAULT_DB_PATH
from incidents.incident_service import IncidentService, incident_api_summary
from runtime.heartbeat import RuntimeHeartbeat
from safety.confirmation_engine import ConfirmationEngine
from safety.escalation_engine import EscalationEngine
from safety.safety_engine import SafetyEngine
from cloud.supabase_sync import start_retry_worker, sync_sensor_event

DEFAULT_USER_NAME = "Sujan M J"
DEFAULT_PREFERRED_NAME = "Sujan"
API_VERSION = "0.4"
AUTH_HEADER = "X-AURA-API-Token"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_STATIC_FILES = {
    "/dashboard": (PROJECT_ROOT / "web" / "dashboard.html", "text/html; charset=utf-8"),
    "/static/dashboard.css": (PROJECT_ROOT / "web" / "dashboard.css", "text/css; charset=utf-8"),
    "/static/dashboard.js": (
        PROJECT_ROOT / "web" / "dashboard.js",
        "application/javascript; charset=utf-8",
    ),
}

_RUNTIME_SPEAKER = None
_RUNTIME_SPEAKER_INITIALIZED = False


def get_runtime_speaker_once():
    global _RUNTIME_SPEAKER, _RUNTIME_SPEAKER_INITIALIZED

    if not _RUNTIME_SPEAKER_INITIALIZED:
        _RUNTIME_SPEAKER = create_runtime_speaker()
        _RUNTIME_SPEAKER_INITIALIZED = True
    return _RUNTIME_SPEAKER


def get_sensor_api_token() -> str | None:
    token = os.environ.get("AURA_SENSOR_API_TOKEN")
    if token:
        stripped = token.strip()
        return stripped if len(stripped) >= 32 else None
    return None


def is_request_authorized(handler: BaseHTTPRequestHandler) -> bool:
    token = get_sensor_api_token()
    if not token:
        return False

    provided = handler.headers.get(AUTH_HEADER)
    return bool(provided) and secrets.compare_digest(provided, token)


def _serialize_event_row(event: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(event)
    if "requires_action" in serialized:
        serialized["requires_action"] = bool(serialized["requires_action"])
    metadata_json = serialized.pop("metadata_json", None)
    if metadata_json:
        try:
            serialized["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError:
            serialized["metadata"] = metadata_json
    return serialized


def beat_sensor_api_heartbeat(
    store: AuraMemoryStore,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        store.apply_schema()
        user_id = store.get_or_create_user(
            name=DEFAULT_USER_NAME,
            preferred_name=DEFAULT_PREFERRED_NAME,
        )
        RuntimeHeartbeat(store, user_id).beat(
            "sensor_api",
            metadata=metadata or {},
        )
    except Exception as exc:
        print(f"AURA_SENSOR_API_HEARTBEAT_ERROR: {exc}")


def process_sensor_event(store: AuraMemoryStore, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    event_bus = DeviceEventBus(store)
    safety_engine = SafetyEngine(store)
    escalation_engine = EscalationEngine(store)
    dispatcher = ActionDispatcher(store, speaker=get_runtime_speaker_once())

    published = event_bus.publish_event(
        user_id,
        event_type=payload["event_type"],
        event_summary=payload["event_summary"],
        source=payload.get("source", "sensor_api"),
        room=payload.get("room"),
        severity=payload.get("severity", "low"),
        confidence=float(payload.get("confidence", 0.5)),
        requires_action=bool(payload.get("requires_action", False)),
        metadata=payload.get("metadata"),
        external_event_id=payload.get("event_uuid"),
    )
    published["room"] = payload.get("room")
    if published.get("duplicate"):
        return {
            "ok": True,
            "event": published,
            "safety": None,
            "escalation": None,
            "confirmation": None,
            "dispatch_results": [],
            "incident": None,
        }

    threading.Thread(
        target=sync_sensor_event,
        args=(published,),
        name="aura-cloud-sensor-sync",
        daemon=True,
    ).start()

    incident_service = IncidentService(store)
    incident = incident_service.create_or_get_for_event(user_id, published)

    safety_result = safety_engine.evaluate_event(user_id, published)
    if safety_result.get("requires_action"):
        incident_service.record_safety_plan(int(incident["id"]), safety_result)

    escalation: dict[str, Any] | None = None
    dispatch_results: list[dict[str, Any]] = []
    confirmation: dict[str, Any] | None = None
    confirmation_engine = ConfirmationEngine(store)

    if safety_result.get("requires_action"):
        escalation_engine.ensure_default_plans(user_id)
        escalation = escalation_engine.build_escalation_response(
            user_id,
            published,
            safety_result,
        )

        spoken_response = escalation.get("spoken_response")
        if spoken_response:
            dispatch_results.append(
                dispatcher.dispatch(
                    user_id,
                    action_type="speak_now",
                    action_summary=spoken_response,
                    target=published.get("room"),
                    source_event_id=published["event_id"],
                    speak_text=spoken_response,
                )
            )

        if escalation.get("requires_user_confirmation"):
            dispatch_results.append(
                dispatcher.dispatch(
                    user_id,
                    action_type="ask_confirmation",
                    action_summary=escalation["first_action"],
                    target=published.get("room"),
                    source_event_id=published["event_id"],
                )
            )
            confirmation = confirmation_engine.create_for_event(
                user_id,
                published,
                escalation,
            )

        second_action = escalation.get("second_action")
        if second_action:
            dispatch_results.append(
                dispatcher.dispatch(
                    user_id,
                    action_type="notify_contact_simulated",
                    action_summary=second_action,
                    target=escalation.get("top_contact"),
                    source_event_id=published["event_id"],
                )
            )

    event_id = int(published["event_id"])
    if safety_result.get("requires_action") and dispatch_results:
        store.update_device_event_action_status(event_id, "dispatched")
    elif not safety_result.get("requires_action"):
        store.update_device_event_action_status(event_id, "ignored")
    else:
        print("AURA_SENSOR_API_EVENT_PENDING_NO_DISPATCH")

    incident = store.get_incident_by_id(int(incident["id"])) or incident
    if dispatch_results:
        incident_service.record_dispatch_results(int(incident["id"]), dispatch_results)
    if confirmation is not None:
        incident_service.record_confirmation_requested(int(incident["id"]), confirmation)

    return {
        "ok": True,
        "event": published,
        "safety": safety_result,
        "escalation": escalation,
        "confirmation": confirmation,
        "dispatch_results": dispatch_results,
        "incident": incident_api_summary(incident),
    }


class AuraSensorAPIHandler(BaseHTTPRequestHandler):
    server_version = "AuraSensorAPI/0.4"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[sensor-api] {self.address_string()} - {format % args}")

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_unauthorized(self) -> None:
        self._send_json(401, {"ok": False, "error": "unauthorized"})

    def _send_web_file(self, path: str) -> bool:
        file_entry = WEB_STATIC_FILES.get(path)
        if file_entry is None:
            return False

        file_path, content_type = file_entry
        resolved = file_path.resolve()
        web_root = (PROJECT_ROOT / "web").resolve()
        if not str(resolved).startswith(str(web_root)):
            return False

        if not resolved.is_file():
            self._send_json(404, {"ok": False, "error": "not_found"})
            return True

        body = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def _require_auth(self) -> bool:
        if is_request_authorized(self):
            return True
        self._send_unauthorized()
        return False

    def _require_sensor_node_auth(self) -> bool:
        store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
        provided = self.headers.get(AUTH_HEADER, "")
        node = store.get_sensor_node_by_token(provided) if len(provided) >= 32 else None
        if node:
            self.authenticated_sensor_node = node
            return True
        self._send_unauthorized()
        return False

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None

        if content_length <= 0:
            return None

        try:
            raw = self.rfile.read(content_length)
            parsed = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        if not isinstance(parsed, dict):
            return None
        return parsed

    def _get_user_id(self, store: AuraMemoryStore) -> int:
        return store.get_or_create_user(
            name=DEFAULT_USER_NAME,
            preferred_name=DEFAULT_PREFERRED_NAME,
        )

    @staticmethod
    def _parse_limit(query: dict[str, list[str]], default: int, maximum: int) -> int:
        try:
            value = int(query.get("limit", [str(default)])[0])
        except (TypeError, ValueError, IndexError):
            value = default
        return max(1, min(value, maximum))

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        if path != "/health" and path not in WEB_STATIC_FILES:
            if not self._require_auth():
                return

        store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
        beat_sensor_api_heartbeat(
            store,
            metadata={"path": self.path, "method": "GET"},
        )

        try:
            if path == "/health":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "service": "aura-sensor-api",
                        "version": API_VERSION,
                    },
                )
                return

            if path == "/nodes/status":
                store.apply_schema()
                user_id = self._get_user_id(store)
                self._send_json(200, {"ok": True, "nodes": store.list_sensor_nodes(user_id)})
                return

            if path in WEB_STATIC_FILES:
                if self._send_web_file(path):
                    return

            if path == "/events/latest":
                if not self._require_auth():
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                events = [
                    _serialize_event_row(event)
                    for event in store.get_recent_device_events(user_id, limit=10)
                ]
                self._send_json(200, {"ok": True, "events": events})
                return

            if path.startswith("/dashboard/"):
                if not self._require_auth():
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                dashboard = DashboardService(store)

                if path == "/dashboard/status":
                    self._send_json(200, dashboard.build_status(user_id))
                    return

                if path == "/dashboard/events":
                    limit = self._parse_limit(query, default=20, maximum=100)
                    self._send_json(200, dashboard.build_events(user_id, limit=limit))
                    return

                if path == "/dashboard/actions":
                    limit = self._parse_limit(query, default=20, maximum=100)
                    self._send_json(200, dashboard.build_actions(user_id, limit=limit))
                    return

                if path == "/dashboard/rooms":
                    limit = self._parse_limit(query, default=50, maximum=200)
                    self._send_json(200, dashboard.build_rooms(user_id, limit=limit))
                    return

            if path == "/confirmations/pending":
                if not self._require_auth():
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                limit = self._parse_limit(query, default=20, maximum=100)
                confirmations = store.get_pending_confirmation_requests(user_id, limit=limit)
                self._send_json(200, {"ok": True, "confirmations": confirmations})
                return

            if path == "/confirmations/recent":
                if not self._require_auth():
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                limit = self._parse_limit(query, default=20, maximum=100)
                confirmations = store.get_recent_confirmation_requests(user_id, limit=limit)
                self._send_json(200, {"ok": True, "confirmations": confirmations})
                return

            if path == "/incidents/recent":
                if not self._require_auth():
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                limit = self._parse_limit(query, default=20, maximum=100)
                incidents = store.get_recent_incidents(user_id, limit=limit)
                self._send_json(200, {"ok": True, "incidents": incidents})
                return

            if path == "/incidents/open":
                if not self._require_auth():
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                limit = self._parse_limit(query, default=20, maximum=100)
                incidents = store.get_open_incidents(user_id, limit=limit)
                self._send_json(200, {"ok": True, "incidents": incidents})
                return

            if path.startswith("/incidents/") and path != "/incidents/recent" and path != "/incidents/open":
                if not self._require_auth():
                    return

                incident_id_str = path.rsplit("/", 1)[-1]
                try:
                    incident_id = int(incident_id_str)
                except ValueError:
                    self._send_json(400, {"ok": False, "error": "invalid_incident_id"})
                    return

                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                incident = store.get_incident_by_id(incident_id)
                if incident is None or int(incident["user_id"]) != user_id:
                    self._send_json(404, {"ok": False, "error": "not_found"})
                    return

                timeline = store.get_incident_timeline_items(incident_id, limit=100)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "incident": incident,
                        "timeline": timeline,
                    },
                )
                return

            self._send_json(404, {"ok": False, "error": "not_found"})
        except Exception as exc:
            print(f"[sensor-api] GET error: {exc}")
            self._send_json(500, {"ok": False, "error": "internal_server_error"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path in ("/nodes/heartbeat", "/rooms/claim"):
            if not self._require_sensor_node_auth():
                return
        elif path == "/events":
            if not is_request_authorized(self) and not self._require_sensor_node_auth():
                return
        elif not self._require_auth():
            return

        store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
        beat_sensor_api_heartbeat(
            store,
            metadata={"path": self.path, "method": "POST"},
        )

        if path in ("/rooms/start", "/rooms/transfer", "/rooms/stop", "/rooms/status", "/rooms/claim"):
            payload = self._read_json_body()
            if payload is None:
                self._send_json(400, {"ok": False, "error": "invalid_json"})
                return
            handoff = RoomHandoff(store)
            try:
                if path == "/rooms/claim":
                    result = handoff.claim(self.headers.get(AUTH_HEADER, ""), payload.get("session_id"),
                                           payload.get("generation"), payload.get("turn_id"))
                else:
                    user_id = self._get_user_id(store)
                    if path == "/rooms/start":
                        result = handoff.start(user_id, payload.get("node_id"), payload.get("approved"))
                    elif path == "/rooms/transfer":
                        result = handoff.transfer(user_id, payload.get("session_id"), payload.get("generation"),
                                                  payload.get("node_id"), payload.get("approved"))
                    elif path == "/rooms/stop":
                        handoff.stop(user_id, payload.get("session_id"), payload.get("generation"))
                        result = None
                    else:
                        result = handoff.status(user_id)
                self._send_json(200, {"ok": True, "session": result})
            except HandoffDenied as exc:
                self._send_json(409, {"ok": False, "error": str(exc)})
            return

        if path == "/nodes/enroll":
            payload = self._read_json_body()
            if payload is None:
                self._send_json(400, {"ok": False, "error": "invalid_json"})
                return
            node_id = payload.get("node_id")
            room = payload.get("room")
            display_name = payload.get("display_name", node_id)
            if (
                not isinstance(node_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", node_id)
                or not isinstance(room, str)
                or not room.strip()
                or len(room.strip()) > 80
                or not isinstance(display_name, str)
                or not display_name.strip()
                or len(display_name.strip()) > 80
            ):
                self._send_json(400, {"ok": False, "error": "invalid_node_registration"})
                return
            try:
                store.apply_schema()
                user_id = self._get_user_id(store)
                node, token = store.enroll_sensor_node(
                    user_id, node_id, display_name.strip(), room.strip()
                )
                self._send_json(
                    201,
                    {
                        "ok": True,
                        "node": node,
                        "token": token,
                        "token_notice": "Copy this token to the node now; it is only returned during enrollment.",
                    },
                )
            except Exception as exc:
                print(f"[sensor-api] POST /nodes/enroll error: {exc}")
                self._send_json(500, {"ok": False, "error": "internal_server_error"})
            return

        if path == "/nodes/revoke":
            payload = self._read_json_body()
            node_id = payload.get("node_id") if payload else None
            if not isinstance(node_id, str) or not node_id.strip():
                self._send_json(400, {"ok": False, "error": "missing_node_id"})
                return
            store.apply_schema()
            user_id = self._get_user_id(store)
            revoked = store.revoke_sensor_node(user_id, node_id.strip())
            self._send_json(200 if revoked else 404, {"ok": revoked, "revoked": revoked})
            return

        if path == "/nodes/heartbeat":
            node = self.authenticated_sensor_node
            payload = self._read_json_body()
            requested_node_id = payload.get("node_id") if payload else None
            if requested_node_id != node["node_id"]:
                self._send_json(403, {"ok": False, "error": "node_identity_mismatch"})
                return
            updated = store.touch_sensor_node(int(node["user_id"]), str(node["node_id"]))
            self._send_json(200 if updated else 401, {"ok": updated, "node_id": node["node_id"]})
            return

        if path == "/confirmations/respond":
            if not self._require_auth():
                return

            payload = self._read_json_body()
            if payload is None:
                self._send_json(400, {"ok": False, "error": "invalid_json"})
                return

            confirmation_id = payload.get("confirmation_id")
            response = payload.get("response")
            if confirmation_id is None or not response:
                self._send_json(
                    400,
                    {"ok": False, "error": "missing_confirmation_id_or_response"},
                )
                return

            try:
                store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
                store.apply_schema()
                user_id = self._get_user_id(store)
                engine = ConfirmationEngine(store)
                result = engine.resolve_confirmation(
                    user_id,
                    int(confirmation_id),
                    str(response),
                )
                self._send_json(200, {"ok": True, "result": result})
            except ValueError as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                print(f"[sensor-api] POST /confirmations/respond error: {exc}")
                self._send_json(500, {"ok": False, "error": "internal_server_error"})
            return

        if path != "/events":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        payload = self._read_json_body()
        if payload is None:
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

        event_type = payload.get("event_type")
        event_summary = payload.get("event_summary")
        if (
            not isinstance(event_type, str)
            or not event_type.strip()
            or not isinstance(event_summary, str)
            or not event_summary.strip()
        ):
            self._send_json(
                400,
                {"ok": False, "error": "missing_event_type_or_summary"},
            )
            return

        event_uuid = payload.get("event_uuid")
        if event_uuid is not None and (
            not isinstance(event_uuid, str)
            or not event_uuid.strip()
            or len(event_uuid.strip()) > 128
        ):
            self._send_json(400, {"ok": False, "error": "invalid_event_uuid"})
            return

        node = getattr(self, "authenticated_sensor_node", None)
        if node:
            if not event_uuid:
                self._send_json(400, {"ok": False, "error": "event_uuid_required_for_node"})
                return
            payload["source"] = node["node_id"]
            payload["room"] = node["room"]

        try:
            store: AuraMemoryStore = self.server.aura_store  # type: ignore[attr-defined]
            store.apply_schema()
            user_id = self._get_user_id(store)
            result = process_sensor_event(store, user_id, payload)
            if node:
                store.touch_sensor_node(int(node["user_id"]), str(node["node_id"]))
            self._send_json(200, result)
        except Exception as exc:
            print(f"[sensor-api] POST /events error: {exc}")
            self._send_json(500, {"ok": False, "error": "internal_server_error"})


def run_server(host: str = "127.0.0.1", port: int = 8787) -> None:
    load_env_file()
    db_path = Path(os.environ.get("AURA_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()
    store = AuraMemoryStore(db_path)
    store.apply_schema()
    start_retry_worker()

    user_id = store.get_or_create_user(
        name=DEFAULT_USER_NAME,
        preferred_name=DEFAULT_PREFERRED_NAME,
    )
    RuntimeHeartbeat(store, user_id).beat(
        "sensor_api",
        metadata={"host": host, "port": port},
    )

    server = HTTPServer((host, port), AuraSensorAPIHandler)
    server.aura_store = store  # type: ignore[attr-defined]

    print(f"AURA_SENSOR_API_STARTING")
    print(f"host={host}")
    print(f"port={port}")
    if not get_sensor_api_token():
        print(
            "AURA_SENSOR_API_AUTH_REQUIRED: protected routes reject requests until "
            "a 32-character AURA_SENSOR_API_TOKEN is configured."
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAURA_SENSOR_API_STOPPED")
    finally:
        store.close()
        server.server_close()
