"""Keep an enrolled AURA sensor node's online heartbeat fresh."""
from __future__ import annotations

import os
import signal
import sys
import threading
from collections.abc import Callable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.check_pi_node_heartbeat_config import validate_environment
from scripts.pi_node_simulator import send_node_heartbeat


def run_heartbeat_loop(
    node_id: str,
    interval_seconds: int,
    stop_event: threading.Event,
    heartbeat: Callable[[str], int] = send_node_heartbeat,
) -> None:
    while not stop_event.is_set():
        heartbeat(node_id)
        stop_event.wait(interval_seconds)


def main() -> int:
    if not validate_environment():
        print(
            "AURA_PI_NODE_HEARTBEAT_SERVICE_ERROR: check node ID, node token, hub URL, "
            "and heartbeat interval configuration"
        )
        return 1

    node_id = os.environ["AURA_SENSOR_NODE_ID"]
    token = os.environ["AURA_SENSOR_NODE_TOKEN"]
    hub_url = os.environ["AURA_SENSOR_API_URL"]
    interval = int(os.environ.get("AURA_SENSOR_NODE_HEARTBEAT_INTERVAL_SECONDS", "30"))
    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_event.set())
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop_event.set())
    print(f"AURA_PI_NODE_HEARTBEAT_SERVICE_START node_id={node_id} interval={interval}s")
    run_heartbeat_loop(
        node_id,
        interval,
        stop_event,
        lambda current_node_id: send_node_heartbeat(current_node_id, hub_url, token),
    )
    print("AURA_PI_NODE_HEARTBEAT_SERVICE_STOP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
