import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.env_loader import load_env_file

DEFAULT_BASE_URL = "http://127.0.0.1:8787"
AUTH_HEADER = "X-AURA-API-Token"


def _request(
    method: str,
    url: str,
    payload: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict]:
    headers = {"Accept": "application/json"}
    if token:
        headers[AUTH_HEADER] = token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"ok": False, "error": body or "http_error"}
        return exc.code, parsed
    except urllib.error.URLError:
        raise


def main() -> None:
    load_env_file()
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    token = os.environ.get("AURA_SENSOR_API_TOKEN")

    try:
        health_status, health_body = _request("GET", f"{base_url}/health")
    except urllib.error.URLError:
        print("AURA_SENSOR_API_EVENT_STATUS_TEST_SKIPPED: server not running")
        return

    if health_status != 200 or not health_body.get("ok"):
        print("AURA_SENSOR_API_EVENT_STATUS_TEST_SKIPPED: server not running")
        return

    post_payload = {
        "event_type": "fall_detected",
        "event_summary": "API event status regression test.",
        "source": "api_event_status_test",
        "room": "bedroom",
        "severity": "high",
        "confidence": 0.82,
        "requires_action": True,
        "metadata": {"test": "api_event_status"},
    }

    post_status, post_body = _request("POST", f"{base_url}/events", post_payload, token=token)
    if post_status != 200 or not post_body.get("ok"):
        print(f"AURA_SENSOR_API_EVENT_STATUS_TEST_FAILED: POST failed with status {post_status}")
        raise SystemExit(1)

    event_id = post_body.get("event", {}).get("event_id")
    if not event_id:
        print("AURA_SENSOR_API_EVENT_STATUS_TEST_FAILED: missing event_id in POST response")
        raise SystemExit(1)

    latest_status, latest_body = _request("GET", f"{base_url}/events/latest", token=token)
    if latest_status != 200 or not latest_body.get("ok"):
        print(f"AURA_SENSOR_API_EVENT_STATUS_TEST_FAILED: GET /events/latest failed ({latest_status})")
        raise SystemExit(1)

    matching = None
    for event in latest_body.get("events", []):
        if int(event.get("id", -1)) == int(event_id):
            matching = event
            break

    if matching is None:
        print(f"AURA_SENSOR_API_EVENT_STATUS_TEST_FAILED: event_id {event_id} not found in latest events")
        raise SystemExit(1)

    actual_status = matching.get("action_status", "none")
    if actual_status != "dispatched":
        print("AURA_SENSOR_API_EVENT_STATUS_TEST_FAILED")
        print("expected=dispatched")
        print(f"actual={actual_status}")
        raise SystemExit(1)

    print("AURA_SENSOR_API_EVENT_STATUS_TEST_OK")


if __name__ == "__main__":
    main()
