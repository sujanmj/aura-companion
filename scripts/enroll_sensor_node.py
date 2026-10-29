"""Enroll or rotate one AURA sensor node credential."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env_loader import load_env_file
from config.sensor_transport import is_safe_sensor_api_url

AUTH_HEADER = "X-AURA-API-Token"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node_id", help="Stable ID, for example pi_bedroom_node")
    parser.add_argument("room", help="Room assigned to this node")
    parser.add_argument("--name", default=None, help="Human-readable node name")
    parser.add_argument("--hub-url", default=None, help="AURA hub URL")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_file()
    hub_url = (args.hub_url or os.environ.get("AURA_SENSOR_API_URL") or "http://127.0.0.1:8787").rstrip("/")
    if not is_safe_sensor_api_url(hub_url):
        print("AURA_SENSOR_NODE_ENROLL_ERROR: hub URL must use HTTPS outside loopback")
        return 1
    token = os.environ.get("AURA_SENSOR_API_TOKEN", "").strip()
    if len(token) < 32:
        print("AURA_SENSOR_NODE_ENROLL_ERROR: configure a 32-character AURA_SENSOR_API_TOKEN on the hub")
        return 1

    payload = {
        "node_id": args.node_id,
        "display_name": args.name or args.node_id,
        "room": args.room,
    }
    request = urllib.request.Request(
        f"{hub_url}/nodes/enroll",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            AUTH_HEADER: token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"AURA_SENSOR_NODE_ENROLL_ERROR: hub returned HTTP {exc.code}")
        return 1
    except urllib.error.URLError:
        print("AURA_SENSOR_NODE_ENROLL_ERROR: hub is unreachable")
        return 1

    node_token = result.get("token")
    if response.status != 201 or not isinstance(node_token, str):
        print("AURA_SENSOR_NODE_ENROLL_ERROR: unexpected hub response")
        return 1
    print(f"AURA_SENSOR_NODE_ID={result['node']['node_id']}")
    print("Copy this one-time credential into config/keys.env on that node only:")
    print(f"AURA_SENSOR_NODE_TOKEN={node_token}")
    print("The hub stores only a hash; enroll again to rotate or replace this credential.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
