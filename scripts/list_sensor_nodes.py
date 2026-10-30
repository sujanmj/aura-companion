"""List enrolled AURA sensor nodes without displaying their credentials."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env_loader import load_env_file
from config.sensor_transport import is_safe_sensor_api_url, open_sensor_api_request

AUTH_HEADER = "X-AURA-API-Token"
DEFAULT_HUB_URL = "http://127.0.0.1:8787"
NODE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def valid_label(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= 80
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def format_node(node: Any) -> str:
    if not isinstance(node, dict):
        raise ValueError("invalid node record")
    node_id = node.get("node_id")
    display_name = node.get("display_name")
    room = node.get("room")
    online = node.get("online")
    last_seen_at = node.get("last_seen_at")
    if (
        not isinstance(node_id, str)
        or not NODE_ID_PATTERN.fullmatch(node_id)
        or not valid_label(display_name)
        or not valid_label(room)
        or type(online) not in (int, bool)
        or online not in (0, 1)
        or (last_seen_at is not None and not valid_label(last_seen_at))
        or (bool(online) and last_seen_at is None)
    ):
        raise ValueError("invalid node record")
    last_seen = last_seen_at if last_seen_at is not None else "never"
    status = "online" if bool(online) else "offline"
    return (
        f"- {node_id} | {display_name.strip()} | room={room.strip()} | "
        f"{status} | last_seen={last_seen}"
    )


def main() -> int:
    load_env_file()
    hub_url = (os.environ.get("AURA_SENSOR_API_URL") or DEFAULT_HUB_URL).rstrip("/")
    if not is_safe_sensor_api_url(hub_url):
        print("AURA_SENSOR_NODE_STATUS_ERROR: hub URL must use HTTPS outside loopback")
        return 1
    token = os.environ.get("AURA_SENSOR_API_TOKEN", "").strip()
    if len(token) < 32:
        print(
            "AURA_SENSOR_NODE_STATUS_ERROR: configure a 32-character "
            "AURA_SENSOR_API_TOKEN on the hub"
        )
        return 1

    request = urllib.request.Request(
        f"{hub_url}/nodes/status",
        headers={"Accept": "application/json", AUTH_HEADER: token},
        method="GET",
    )
    try:
        with open_sensor_api_request(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        print(f"AURA_SENSOR_NODE_STATUS_ERROR: hub returned HTTP {status}")
        return 1
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
        print("AURA_SENSOR_NODE_STATUS_ERROR: hub response unavailable")
        return 1

    if response.status != 200 or not isinstance(result, dict) or result.get("ok") is not True:
        print("AURA_SENSOR_NODE_STATUS_ERROR: hub returned an invalid response")
        return 1
    nodes = result.get("nodes")
    if not isinstance(nodes, list):
        print("AURA_SENSOR_NODE_STATUS_ERROR: hub returned invalid node data")
        return 1
    try:
        lines = [format_node(node) for node in nodes]
    except ValueError:
        print("AURA_SENSOR_NODE_STATUS_ERROR: hub returned invalid node data")
        return 1
    print("AURA_SENSOR_NODES")
    if not lines:
        print("- (none enrolled)")
    else:
        print("\n".join(lines))
    print(
        "Online means a heartbeat or event was seen in the last 90 seconds; "
        "it does not confirm sensor or playback operation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
