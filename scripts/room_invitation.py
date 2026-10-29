"""Manage short-lived, owner-approved room invitations for AURA."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
import sys
import urllib.error
import urllib.request
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env_loader import load_env_file
from config.sensor_transport import is_safe_sensor_api_url

AUTH_HEADER = "X-AURA-API-Token"
DEFAULT_HUB_URL = "http://127.0.0.1:8787"


class InvitationClientError(RuntimeError):
    pass


def post_invitation_request(
    hub_url: str,
    token: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if len(token) < 32 or token.strip() != token:
        raise InvitationClientError("set AURA_SENSOR_API_TOKEN to the hub administrator credential")
    if action not in {"start", "transfer", "status", "stop"}:
        raise InvitationClientError("unsupported invitation action")
    base_url = hub_url.rstrip("/")
    if not is_safe_sensor_api_url(base_url):
        raise InvitationClientError("hub URL must use HTTPS outside loopback")
    request = urllib.request.Request(
        f"{base_url}/rooms/{action}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", AUTH_HEADER: token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise InvitationClientError(f"hub rejected invitation request (HTTP {status})") from None
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError):
        raise InvitationClientError(
            "hub response unavailable; check invitation status before trying again"
        ) from None
    if response.status != 200 or not isinstance(result, dict) or result.get("ok") is not True:
        raise InvitationClientError("hub returned an invalid invitation response")
    return result


def confirmed(expected: str, prompt: str) -> bool:
    try:
        return input(prompt) == expected
    except EOFError:
        return False


def session_summary(session: dict[str, Any] | None) -> str:
    if session is None:
        return "No active room invitation."
    node_id = session.get("node_id")
    session_id = session.get("session_id")
    generation = session.get("generation")
    expires_at = session.get("expires_at")
    if (
        not isinstance(node_id, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", node_id)
        or not isinstance(session_id, str)
        or not re.fullmatch(r"[A-Fa-f0-9-]{1,64}", session_id)
        or type(generation) is not int
        or generation < 1
        or isinstance(expires_at, bool)
        or not isinstance(expires_at, (float, int))
        or not math.isfinite(expires_at)
    ):
        raise ValueError("invalid invitation fields")
    return (
        f"Room invitation: node={node_id} "
        f"session_id={session_id} generation={generation} "
        f"expires_at={expires_at}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("status", help="Show the current invitation")
    start = subparsers.add_parser("start", help="Invite one enrolled, online room node")
    start.add_argument("node_id")
    transfer = subparsers.add_parser("transfer", help="Move the invitation to another node")
    transfer.add_argument("session_id")
    transfer.add_argument("generation", type=int)
    transfer.add_argument("node_id")
    stop = subparsers.add_parser("stop", help="End the current invitation")
    stop.add_argument("session_id")
    stop.add_argument("generation", type=int)
    parser.add_argument("--hub-url", default=None, help="Hub URL (default: AURA_SENSOR_API_URL or loopback)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env_file()
    token = os.environ.get("AURA_SENSOR_API_TOKEN", "")
    hub_url = (args.hub_url or os.environ.get("AURA_SENSOR_API_URL") or DEFAULT_HUB_URL).rstrip("/")
    if len(token) < 32 or token.strip() != token:
        print("AURA_ROOM_INVITATION_ERROR: set AURA_SENSOR_API_TOKEN to the hub administrator credential")
        return 1
    if not is_safe_sensor_api_url(hub_url):
        print("AURA_ROOM_INVITATION_ERROR: hub URL must use HTTPS outside loopback")
        return 1

    if args.action == "start":
        expected = f"INVITE {args.node_id}"
        prompt = f"Type {expected} to invite this enrolled room for up to five minutes: "
        if not confirmed(expected, prompt):
            print("AURA_ROOM_INVITATION_CANCELLED")
            return 1
        payload = {"node_id": args.node_id, "approved": True}
    elif args.action == "transfer":
        expected = f"TRANSFER {args.node_id}"
        prompt = f"Type {expected} to move the current invitation to this room: "
        if not confirmed(expected, prompt):
            print("AURA_ROOM_INVITATION_CANCELLED")
            return 1
        payload = {
            "session_id": args.session_id,
            "generation": args.generation,
            "node_id": args.node_id,
            "approved": True,
        }
    elif args.action == "stop":
        expected = f"STOP {args.session_id}"
        if not confirmed(expected, f"Type {expected} to end the invitation now: "):
            print("AURA_ROOM_INVITATION_CANCELLED")
            return 1
        payload = {"session_id": args.session_id, "generation": args.generation}
    else:
        payload = {}

    try:
        response = post_invitation_request(hub_url, token, args.action, payload)
    except InvitationClientError as exc:
        print(f"AURA_ROOM_INVITATION_ERROR: {exc}")
        return 1

    if args.action == "stop":
        print("AURA_ROOM_INVITATION_STOPPED")
        return 0
    session = response.get("session")
    if session is not None and not isinstance(session, dict):
        print("AURA_ROOM_INVITATION_ERROR: hub returned invalid invitation data")
        return 1
    try:
        print(session_summary(session))
    except ValueError:
        print("AURA_ROOM_INVITATION_ERROR: hub returned invalid invitation data")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
