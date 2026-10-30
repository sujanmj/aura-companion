import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.env_loader import load_env_file
from memory.sqlite_store import AuraMemoryStore
from runtime.heartbeat import build_runtime_health
from config.sensor_transport import is_safe_sensor_api_url, open_sensor_api_request

DEFAULT_BASE_URL = "http://127.0.0.1:8787"
AUTH_HEADER = "X-AURA-API-Token"
DEFAULT_USER_NAME = "Sujan M J"
DEFAULT_PREFERRED_NAME = "Sujan"


def _request(url: str, token: str | None, timeout: int) -> int:
    headers = {"Accept": "application/json"}
    if token:
        headers[AUTH_HEADER] = token
    request = urllib.request.Request(url, headers=headers, method="GET")
    with open_sensor_api_request(request, timeout=timeout) as response:
        return response.status


def main() -> None:
    load_env_file()
    base_url = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL).rstrip("/")
    token = os.environ.get("AURA_SENSOR_API_TOKEN")
    if not is_safe_sensor_api_url(base_url):
        print("AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_FAILED: hub URL must use HTTPS outside loopback")
        raise SystemExit(1)

    try:
        if _request(f"{base_url}/health", token, timeout=5) != 200:
            print("AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_SKIPPED: server not running")
            return
    except urllib.error.URLError:
        print("AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_SKIPPED: server not running")
        return

    try:
        if _request(f"{base_url}/dashboard/status", token, timeout=15) != 200:
            print("AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_FAILED: dashboard/status not ok")
            raise SystemExit(1)
    except urllib.error.URLError as exc:
        print(f"AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_FAILED: {exc}")
        raise SystemExit(1)

    store = AuraMemoryStore()
    store.apply_schema()
    user_id = store.get_or_create_user(
        name=DEFAULT_USER_NAME,
        preferred_name=DEFAULT_PREFERRED_NAME,
    )
    runtime_health = build_runtime_health(store, user_id)
    store.close()

    sensor_api = next(
        (
            service
            for service in runtime_health.get("services", [])
            if service.get("service_name") == "sensor_api"
        ),
        None,
    )

    if sensor_api is None:
        print("AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_FAILED: sensor_api missing")
        raise SystemExit(1)

    if sensor_api.get("effective_status") != "online":
        print(
            "AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_FAILED: "
            f"sensor_api effective_status={sensor_api.get('effective_status')}"
        )
        raise SystemExit(1)

    print("AURA_RUNTIME_DASHBOARD_HEARTBEAT_TEST_OK")


if __name__ == "__main__":
    main()
