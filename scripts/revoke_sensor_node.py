"""Revoke one enrolled AURA sensor node after typed owner confirmation."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env_loader import load_env_file
from config.sensor_transport import is_safe_sensor_api_url, open_sensor_api_request

AUTH_HEADER = "X-AURA-API-Token"
NODE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node_id", help="Enrolled node ID to revoke")
    parser.add_argument("--hub-url", default=None, help="AURA hub URL")
    return parser.parse_args(argv)


def confirmed(node_id: str) -> bool:
    try:
        return input(f"Type REVOKE {node_id} to disable this node credential: ") == f"REVOKE {node_id}"
    except EOFError:
        return False


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not NODE_ID_PATTERN.fullmatch(args.node_id):
        print("AURA_SENSOR_NODE_REVOKE_ERROR: invalid node ID")
        return 1
    if not confirmed(args.node_id):
        print("AURA_SENSOR_NODE_REVOKE_CANCELLED")
        return 1

    load_env_file()
    hub_url = (args.hub_url or os.environ.get("AURA_SENSOR_API_URL") or "http://127.0.0.1:8787").rstrip("/")
    if not is_safe_sensor_api_url(hub_url):
        print("AURA_SENSOR_NODE_REVOKE_ERROR: hub URL must use HTTPS outside loopback")
        return 1
    token = os.environ.get("AURA_SENSOR_API_TOKEN", "").strip()
    if len(token) < 32:
        print("AURA_SENSOR_NODE_REVOKE_ERROR: configure a 32-character AURA_SENSOR_API_TOKEN on the hub")
        return 1

    request = urllib.request.Request(
        f"{hub_url}/nodes/revoke",
        data=json.dumps({"node_id": args.node_id}).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            AUTH_HEADER: token,
        },
        method="POST",
    )
    try:
        with open_sensor_api_request(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        print(f"AURA_SENSOR_NODE_REVOKE_ERROR: hub returned HTTP {status}")
        return 1
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
        print("AURA_SENSOR_NODE_REVOKE_ERROR: hub response unavailable; verify node status before retrying")
        return 1

    if response.status != 200 or not isinstance(result, dict) or result.get("ok") is not True or result.get("revoked") is not True:
        print("AURA_SENSOR_NODE_REVOKE_ERROR: hub did not confirm revocation")
        return 1
    print(f"AURA_SENSOR_NODE_REVOKED={args.node_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
