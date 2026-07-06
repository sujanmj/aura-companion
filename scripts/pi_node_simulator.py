from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.env_loader import load_env_file

AUTH_HEADER = "X-AURA-API-Token"
DEFAULT_HUB_URL = "http://127.0.0.1:8787"

NODE_PRESETS: dict[str, dict[str, Any]] = {
    "bedroom": {
        "source": "pi_bedroom_node",
        "room": "bedroom",
        "events": ("fall_detected", "sleep_unusual", "movement_absent"),
    },
    "kitchen": {
        "source": "pi_kitchen_node",
        "room": "kitchen",
        "events": (
            "smoke_detected",
            "fire_detected",
            "gas_leak_detected",
            "water_leak_detected",
        ),
    },
    "balcony": {
        "source": "pi_balcony_plant_node",
        "room": "balcony",
        "events": ("plant_moisture_low", "plant_moisture_ok", "water_tank_low"),
    },
    "front_door": {
        "source": "pi_front_door_node",
        "room": "front_door",
        "events": (
            "unknown_person_detected",
            "unknown_person_with_possible_weapon",
            "known_person_detected",
            "door_left_open",
        ),
    },
    "medicine": {
        "source": "medicine_schedule_node",
        "room": "bedroom",
        "events": ("pill_missed", "pill_taken"),
    },
    "health": {
        "source": "wearable_bridge_node",
        "room": "user",
        "events": ("heart_rate_high", "heart_rate_low", "no_movement_detected"),
    },
}

EVENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "fall_detected": {
        "severity": "high",
        "confidence": 0.82,
        "requires_action": True,
        "summary": "Possible fall detected in bedroom.",
    },
    "smoke_detected": {
        "severity": "critical",
        "confidence": 0.88,
        "requires_action": True,
        "summary": "Possible smoke detected in kitchen.",
    },
    "fire_detected": {
        "severity": "critical",
        "confidence": 0.9,
        "requires_action": True,
        "summary": "Possible fire detected in kitchen.",
    },
    "gas_leak_detected": {
        "severity": "critical",
        "confidence": 0.86,
        "requires_action": True,
        "summary": "Possible gas leak detected in kitchen.",
    },
    "water_leak_detected": {
        "severity": "medium",
        "confidence": 0.78,
        "requires_action": True,
        "summary": "Possible water leak detected.",
    },
    "plant_moisture_low": {
        "severity": "low",
        "confidence": 0.8,
        "requires_action": True,
        "summary": "Balcony plant soil moisture is low.",
    },
    "unknown_person_detected": {
        "severity": "medium",
        "confidence": 0.75,
        "requires_action": True,
        "summary": "Unknown person detected near front door.",
    },
    "unknown_person_with_possible_weapon": {
        "severity": "high",
        "confidence": 0.7,
        "requires_action": True,
        "summary": "Unknown person with possible weapon-like object near front door.",
    },
    "pill_missed": {
        "severity": "medium",
        "confidence": 0.8,
        "requires_action": True,
        "summary": "Scheduled medicine may have been missed.",
    },
    "heart_rate_high": {
        "severity": "high",
        "confidence": 0.8,
        "requires_action": True,
        "summary": "Heart rate is unusually high.",
    },
}


def get_hub_url() -> str:
    return os.environ.get("AURA_SENSOR_API_URL", DEFAULT_HUB_URL).rstrip("/")


def print_supported_nodes() -> None:
    print("AURA_PI_NODE_SIMULATOR_NODES")
    for node_name, preset in NODE_PRESETS.items():
        events = ", ".join(preset["events"])
        print(f"- {node_name}: source={preset['source']} room={preset['room']}")
        print(f"  events: {events}")


def build_payload(
    node: str,
    event_type: str,
    confidence: float | None = None,
    source: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    preset = NODE_PRESETS[node]
    room = preset["room"]
    event_source = source or preset["source"]

    if event_type in EVENT_TEMPLATES:
        template = EVENT_TEMPLATES[event_type]
        event_summary = summary or template["summary"]
        severity = template["severity"]
        event_confidence = confidence if confidence is not None else template["confidence"]
        requires_action = template["requires_action"]
    else:
        event_summary = summary or f"{event_type} reported by {event_source}"
        severity = "low"
        event_confidence = confidence if confidence is not None else 0.5
        requires_action = False

    return {
        "event_type": event_type,
        "event_summary": event_summary,
        "source": event_source,
        "room": room,
        "severity": severity,
        "confidence": event_confidence,
        "requires_action": requires_action,
        "metadata": {
            "simulator": True,
            "node": node,
            "event": event_type,
        },
    }


def post_event(hub_url: str, payload: dict[str, Any], token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers[AUTH_HEADER] = token

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{hub_url}/events",
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise PermissionError("unauthorized") from exc
        raise
    except urllib.error.URLError as exc:
        raise ConnectionError("server not running") from exc


def send_simulated_event(
    node: str,
    event_type: str,
    hub_url: str | None = None,
    confidence: float | None = None,
    source: str | None = None,
    summary: str | None = None,
) -> int:
    load_env_file()
    resolved_hub_url = (hub_url or get_hub_url()).rstrip("/")
    token = os.environ.get("AURA_SENSOR_API_TOKEN")

    if token:
        print(f"AURA_PI_NODE_TOKEN_PREFIX={token[:8]}")
    else:
        print("AURA_PI_NODE_AUTH_WARNING: no AURA_SENSOR_API_TOKEN configured")

    if node not in NODE_PRESETS:
        print(f"AURA_PI_NODE_SIMULATOR_ERROR: unknown node '{node}'")
        return 1

    preset = NODE_PRESETS[node]
    if event_type not in preset["events"]:
        supported = ", ".join(preset["events"])
        print(
            f"AURA_PI_NODE_SIMULATOR_ERROR: event '{event_type}' not supported "
            f"for node '{node}'. Supported: {supported}"
        )
        return 1

    payload = build_payload(node, event_type, confidence, source, summary)

    print("AURA_PI_NODE_SIMULATOR_SEND")
    print(f"node={node}")
    print(f"event_type={event_type}")
    print(f"hub_url={resolved_hub_url}")
    print(f"payload={json.dumps(payload)}")
    try:
        response = post_event(resolved_hub_url, payload, token)
    except PermissionError:
        print("AURA_PI_NODE_SIMULATOR_ERROR: unauthorized - check AURA_SENSOR_API_TOKEN")
        return 1
    except ConnectionError:
        print("AURA_PI_NODE_SIMULATOR_ERROR: server not running")
        return 1
    except Exception as exc:
        print(f"AURA_PI_NODE_SIMULATOR_ERROR: {exc}")
        return 1

    print(f"response={json.dumps(response, default=str)}")
    print("AURA_PI_NODE_SIMULATOR_OK")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate Raspberry Pi / sensor nodes sending events to AURA Sensor API.",
    )
    parser.add_argument("node", nargs="?", help="Node preset name (e.g. bedroom, kitchen)")
    parser.add_argument("event_type", nargs="?", help="Event type to send")
    parser.add_argument(
        "--hub-url",
        default=None,
        help="AURA hub URL (default: AURA_SENSOR_API_URL or http://127.0.0.1:8787)",
    )
    parser.add_argument("--confidence", type=float, default=None, help="Override confidence")
    parser.add_argument("--source", default=None, help="Override source identifier")
    parser.add_argument("--summary", default=None, help="Override event summary")
    parser.add_argument("--loop", type=int, default=1, help="Send event N times")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between loop sends")
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show supported rooms/events and exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.list:
        print_supported_nodes()
        return 0

    if not args.node or not args.event_type:
        print("Usage: python scripts/pi_node_simulator.py <node> <event_type>")
        print("       python scripts/pi_node_simulator.py --list")
        return 1

    loop_count = max(1, args.loop)
    for attempt in range(loop_count):
        if attempt > 0:
            time.sleep(max(0.0, args.delay))

        exit_code = send_simulated_event(
            args.node,
            args.event_type,
            hub_url=args.hub_url,
            confidence=args.confidence,
            source=args.source,
            summary=args.summary,
        )
        if exit_code != 0:
            return exit_code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
