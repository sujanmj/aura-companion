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
        print("AURA_INCIDENT_API_TEST_SKIPPED: server not running")
        return

    if health_status != 200 or not health_body.get("ok"):
        print("AURA_INCIDENT_API_TEST_SKIPPED: server not running")
        return

    event_payload = {
        "event_type": "fall_detected",
        "event_summary": "Incident API test fall event.",
        "source": "incident_api_test",
        "room": "bedroom",
        "severity": "high",
        "confidence": 0.88,
        "requires_action": True,
    }

    try:
        post_status, post_body = _request(
            "POST",
            f"{base_url}/events",
            event_payload,
            token=token,
        )
        recent_status, recent_body = _request("GET", f"{base_url}/incidents/recent", token=token)
    except urllib.error.URLError:
        print("AURA_INCIDENT_API_TEST_SKIPPED: server not running")
        return

    if post_status != 200 or not post_body.get("ok"):
        print(f"AURA_INCIDENT_API_TEST_FAILED: POST /events returned {post_status}")
        raise SystemExit(1)

    incident = post_body.get("incident")
    if not incident or incident.get("id") is None:
        print("AURA_INCIDENT_API_TEST_FAILED: expected incident in POST /events response")
        raise SystemExit(1)

    incident_id = incident["id"]

    if recent_status != 200 or not recent_body.get("ok"):
        print(f"AURA_INCIDENT_API_TEST_FAILED: GET /incidents/recent returned {recent_status}")
        raise SystemExit(1)

    recent_ids = {item.get("id") for item in recent_body.get("incidents", [])}
    if incident_id not in recent_ids:
        print("AURA_INCIDENT_API_TEST_FAILED: incident not in recent list")
        raise SystemExit(1)

    detail_status, detail_body = _request(
        "GET",
        f"{base_url}/incidents/{incident_id}",
        token=token,
    )

    if detail_status != 200 or not detail_body.get("ok"):
        print(f"AURA_INCIDENT_API_TEST_FAILED: GET /incidents/{incident_id} returned {detail_status}")
        raise SystemExit(1)

    timeline = detail_body.get("timeline") or []
    item_types = {item.get("item_type") for item in timeline}
    if "event_received" not in item_types:
        print("AURA_INCIDENT_API_TEST_FAILED: timeline missing event_received")
        raise SystemExit(1)
    if "dispatch" not in item_types:
        print("AURA_INCIDENT_API_TEST_FAILED: timeline missing dispatch")
        raise SystemExit(1)

    print("AURA_INCIDENT_API_TEST_OK")


if __name__ == "__main__":
    main()
