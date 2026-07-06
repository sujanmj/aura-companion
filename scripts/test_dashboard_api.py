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


def _request(method: str, url: str, token: str | None = None) -> tuple[int, dict]:
    headers = {"Accept": "application/json"}
    if token:
        headers[AUTH_HEADER] = token

    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.URLError:
        raise


def main() -> None:
    load_env_file()
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    token = os.environ.get("AURA_SENSOR_API_TOKEN")

    try:
        health_status, health_body = _request("GET", f"{base_url}/health")
    except urllib.error.URLError:
        print("AURA_DASHBOARD_API_TEST_SKIPPED: server not running")
        return

    if health_status != 200 or not health_body.get("ok"):
        print("AURA_DASHBOARD_API_TEST_SKIPPED: server not running")
        return

    try:
        status_code, status_body = _request("GET", f"{base_url}/dashboard/status", token=token)
        events_code, events_body = _request("GET", f"{base_url}/dashboard/events", token=token)
        actions_code, actions_body = _request("GET", f"{base_url}/dashboard/actions", token=token)
        rooms_code, rooms_body = _request("GET", f"{base_url}/dashboard/rooms", token=token)
    except urllib.error.URLError:
        print("AURA_DASHBOARD_API_TEST_SKIPPED: server not running")
        return

    for label, code, body in (
        ("status", status_code, status_body),
        ("events", events_code, events_body),
        ("actions", actions_code, actions_body),
        ("rooms", rooms_code, rooms_body),
    ):
        if code != 200 or not body.get("ok"):
            print(f"AURA_DASHBOARD_API_TEST_FAILED: {label} returned {code}")
            raise SystemExit(1)

    if status_body.get("service") != "aura-dashboard":
        print("AURA_DASHBOARD_API_TEST_FAILED: unexpected service name")
        raise SystemExit(1)

    if "summary" not in status_body:
        print("AURA_DASHBOARD_API_TEST_FAILED: summary missing")
        raise SystemExit(1)

    if "latest_events" not in status_body:
        print("AURA_DASHBOARD_API_TEST_FAILED: latest_events missing")
        raise SystemExit(1)

    if "rooms" not in status_body:
        print("AURA_DASHBOARD_API_TEST_FAILED: rooms missing")
        raise SystemExit(1)

    summary = status_body["summary"]
    print("AURA_DASHBOARD_API_TEST_OK")
    print("DASHBOARD SUMMARY:")
    print(f"recent_event_count={summary.get('recent_event_count')}")
    print(f"pending_event_count={summary.get('pending_event_count')}")
    print(f"recent_action_count={summary.get('recent_action_count')}")
    print(f"rooms_active_count={summary.get('rooms_active_count')}")
    print(f"critical_or_high_event_count={summary.get('critical_or_high_event_count')}")


if __name__ == "__main__":
    main()
