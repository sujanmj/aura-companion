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
        print("AURA_CONFIRMATION_API_TEST_SKIPPED: server not running")
        return

    if health_status != 200 or not health_body.get("ok"):
        print("AURA_CONFIRMATION_API_TEST_SKIPPED: server not running")
        return

    event_payload = {
        "event_type": "fall_detected",
        "event_summary": "Confirmation API test fall event.",
        "source": "confirmation_api_test",
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
        pending_status, pending_body = _request(
            "GET",
            f"{base_url}/confirmations/pending",
            token=token,
        )
    except urllib.error.URLError:
        print("AURA_CONFIRMATION_API_TEST_SKIPPED: server not running")
        return

    if post_status != 200 or not post_body.get("ok"):
        print(f"AURA_CONFIRMATION_API_TEST_FAILED: POST /events returned {post_status}")
        raise SystemExit(1)

    confirmation = post_body.get("confirmation")
    if not confirmation or confirmation.get("status") != "pending":
        print("AURA_CONFIRMATION_API_TEST_FAILED: expected pending confirmation in POST /events")
        raise SystemExit(1)

    confirmation_id = confirmation.get("id")
    if confirmation_id is None:
        print("AURA_CONFIRMATION_API_TEST_FAILED: confirmation id missing")
        raise SystemExit(1)

    if pending_status != 200 or not pending_body.get("ok"):
        print(f"AURA_CONFIRMATION_API_TEST_FAILED: GET /confirmations/pending returned {pending_status}")
        raise SystemExit(1)

    pending_ids = {item.get("id") for item in pending_body.get("confirmations", [])}
    if confirmation_id not in pending_ids:
        print("AURA_CONFIRMATION_API_TEST_FAILED: confirmation not in pending list")
        raise SystemExit(1)

    respond_status, respond_body = _request(
        "POST",
        f"{base_url}/confirmations/respond",
        {"confirmation_id": confirmation_id, "response": "ok"},
        token=token,
    )

    if respond_status != 200 or not respond_body.get("ok"):
        print(f"AURA_CONFIRMATION_API_TEST_FAILED: POST /confirmations/respond returned {respond_status}")
        raise SystemExit(1)

    result = respond_body.get("result") or {}
    if result.get("status") != "confirmed_ok":
        print("AURA_CONFIRMATION_API_TEST_FAILED: expected confirmed_ok result")
        raise SystemExit(1)

    print("AURA_CONFIRMATION_API_TEST_OK")


if __name__ == "__main__":
    main()
