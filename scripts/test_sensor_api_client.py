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


def _build_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers[AUTH_HEADER] = token
    return headers


def _request(
    method: str,
    url: str,
    payload: dict | None = None,
    token: str | None = None,
) -> dict:
    data = None
    headers = _build_headers(token)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    load_env_file()
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    token = os.environ.get("AURA_SENSOR_API_TOKEN")

    if not token:
        print("AURA_SENSOR_API_CLIENT_AUTH_WARNING: no token configured")

    try:
        health = _request("GET", f"{base_url}/health")
        event_payload = {
            "event_type": "fall_detected",
            "event_summary": "Possible fall detected in bedroom from API test.",
            "source": "api_test_client",
            "room": "bedroom",
            "severity": "high",
            "confidence": 0.82,
            "requires_action": True,
            "metadata": {"test": True},
        }
        post_response = _request("POST", f"{base_url}/events", event_payload, token=token)
        latest = _request("GET", f"{base_url}/events/latest", token=token)
    except urllib.error.URLError:
        print("AURA_SENSOR_API_CLIENT_ERROR: server not running")
        return
    except Exception as exc:
        print(f"AURA_SENSOR_API_CLIENT_ERROR: {exc}")
        return

    print("AURA_SENSOR_API_CLIENT_TEST_OK")
    print("HEALTH:")
    print(json.dumps(health, indent=2))
    print("POST EVENT RESPONSE:")
    print(json.dumps(post_response, indent=2, default=str))
    print("LATEST EVENTS:")
    print(json.dumps(latest, indent=2, default=str))


if __name__ == "__main__":
    main()
