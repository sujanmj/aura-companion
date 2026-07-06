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
    data = None
    headers = {"Accept": "application/json"}
    if token:
        headers[AUTH_HEADER] = token
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
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

    if not token:
        print("AURA_SENSOR_API_AUTH_TEST_SKIPPED")
        print("Set AURA_SENSOR_API_TOKEN in config/keys.env to test auth.")
        return

    event_payload = {
        "event_type": "pill_missed",
        "event_summary": "Auth test event from sensor API auth script.",
        "source": "api_auth_test",
        "room": "bedroom",
        "severity": "medium",
        "confidence": 0.5,
        "requires_action": True,
    }

    try:
        health_status, health_body = _request("GET", f"{base_url}/health")
        latest_status, latest_body = _request("GET", f"{base_url}/events/latest")
        post_status, post_body = _request("POST", f"{base_url}/events", event_payload)
        post_auth_status, post_auth_body = _request(
            "POST",
            f"{base_url}/events",
            event_payload,
            token=token,
        )
    except urllib.error.URLError:
        print("AURA_SENSOR_API_AUTH_TEST_ERROR: server not running")
        return

    if health_status != 200 or not health_body.get("ok"):
        print(f"AURA_SENSOR_API_AUTH_TEST_ERROR: unexpected health response {health_status}")
        return
    if latest_status != 401 or latest_body.get("error") != "unauthorized":
        print(f"AURA_SENSOR_API_AUTH_TEST_ERROR: expected 401 for /events/latest, got {latest_status}")
        return
    if post_status != 401 or post_body.get("error") != "unauthorized":
        print(f"AURA_SENSOR_API_AUTH_TEST_ERROR: expected 401 for POST /events, got {post_status}")
        return
    if post_auth_status != 200 or not post_auth_body.get("ok"):
        print(f"AURA_SENSOR_API_AUTH_TEST_ERROR: expected 200 for authed POST, got {post_auth_status}")
        return

    print("AURA_SENSOR_API_AUTH_TEST_OK")


if __name__ == "__main__":
    main()
