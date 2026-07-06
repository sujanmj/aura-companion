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


def main() -> None:
    load_env_file()
    base_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_URL
    token = os.environ.get("AURA_SENSOR_API_TOKEN")

    headers = {"Accept": "application/json"}
    if token:
        headers[AUTH_HEADER] = token

    request = urllib.request.Request(
        f"{base_url}/dashboard/status",
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        print("AURA_DASHBOARD_STATUS_ERROR: server not running")
        return

    print("AURA_DASHBOARD_STATUS")
    summary = body.get("summary", {})

    print("\nSummary:")
    for key, value in summary.items():
        print(f"- {key}: {value}")

    print("\nRecent events:")
    for event in body.get("latest_events", [])[:10]:
        print(
            f"- {event.get('id')} | {event.get('event_type')} | {event.get('severity')} | "
            f"room={event.get('room') or 'unknown'} | status={event.get('action_status')}"
        )

    print("\nPending events:")
    pending = body.get("pending_events", [])
    if not pending:
        print("- (none)")
    else:
        for event in pending[:10]:
            print(
                f"- {event.get('id')} | {event.get('event_type')} | "
                f"room={event.get('room') or 'unknown'}"
            )

    print("\nRecent actions:")
    for action in body.get("recent_actions", [])[:10]:
        print(
            f"- {action.get('id')} | {action.get('action_type')} | "
            f"status={action.get('status')}"
        )

    print("\nActive rooms:")
    for room in body.get("rooms", [])[:10]:
        print(
            f"- {room.get('room')} | events={room.get('event_count')} | "
            f"severity={room.get('highest_severity')} | pending={room.get('pending_count')}"
        )

    print("\nCritical/high alerts:")
    alerts = body.get("critical_alerts", [])
    if not alerts:
        print("- (none)")
    else:
        for alert in alerts:
            print(
                f"- {alert.get('event_id')} | {alert.get('event_type')} | "
                f"{alert.get('severity')} | room={alert.get('room')} | "
                f"status={alert.get('action_status')}"
            )


if __name__ == "__main__":
    main()
