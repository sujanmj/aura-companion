import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE_URL = "http://127.0.0.1:8787"


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL

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
        post_response = _request("POST", f"{base_url}/events", event_payload)
        latest = _request("GET", f"{base_url}/events/latest")
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
