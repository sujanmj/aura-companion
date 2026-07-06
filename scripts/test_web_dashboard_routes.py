import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE_URL = "http://127.0.0.1:8787"


def _fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, response.read().decode("utf-8")


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL

    try:
        health_status, _ = _fetch(f"{base_url}/health")
    except urllib.error.URLError:
        print("AURA_WEB_DASHBOARD_TEST_SKIPPED: server not running")
        return

    if health_status != 200:
        print("AURA_WEB_DASHBOARD_TEST_SKIPPED: server not running")
        return

    try:
        dashboard_status, dashboard_body = _fetch(f"{base_url}/dashboard")
        css_status, css_body = _fetch(f"{base_url}/static/dashboard.css")
        js_status, js_body = _fetch(f"{base_url}/static/dashboard.js")
    except urllib.error.URLError:
        print("AURA_WEB_DASHBOARD_TEST_SKIPPED: server not running")
        return

    if dashboard_status != 200 or "AURA Command Center" not in dashboard_body:
        print("AURA_WEB_DASHBOARD_ROUTES_TEST_FAILED: /dashboard")
        raise SystemExit(1)

    if css_status != 200 or "severity-critical" not in css_body:
        print("AURA_WEB_DASHBOARD_ROUTES_TEST_FAILED: /static/dashboard.css")
        raise SystemExit(1)

    if js_status != 200 or "AURA_SENSOR_API_TOKEN" not in js_body:
        print("AURA_WEB_DASHBOARD_ROUTES_TEST_FAILED: /static/dashboard.js")
        raise SystemExit(1)

    print("AURA_WEB_DASHBOARD_ROUTES_TEST_OK")


if __name__ == "__main__":
    main()
