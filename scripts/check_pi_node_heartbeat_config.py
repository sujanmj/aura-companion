"""Validate configuration before starting an enrolled Pi node heartbeat service."""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from urllib.parse import urlparse


def validate_environment(environment: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environment is None else environment
    token = values.get("AURA_SENSOR_NODE_TOKEN", "")
    node_id = values.get("AURA_SENSOR_NODE_ID", "")
    hub_url = values.get("AURA_SENSOR_API_URL", "")
    try:
        interval = int(values.get("AURA_SENSOR_NODE_HEARTBEAT_INTERVAL_SECONDS", "30"))
    except (TypeError, ValueError):
        return False

    if not isinstance(hub_url, str):
        return False
    try:
        parsed_url = urlparse(hub_url)
    except ValueError:
        return False
    return (
        len(token) >= 32
        and token.strip() == token
        and len(set(token)) > 1
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", node_id) is not None
        and parsed_url.scheme in {"http", "https"}
        and bool(parsed_url.hostname)
        and parsed_url.username is None
        and parsed_url.password is None
        and parsed_url.path in {"", "/"}
        and not parsed_url.query
        and not parsed_url.fragment
        and 5 <= interval <= 60
    )


if __name__ == "__main__":
    if not validate_environment():
        import sys

        print(
            "AURA Pi node heartbeat configuration invalid: set an enrolled node ID, "
            "a private node token, a valid AURA_SENSOR_API_URL, and an interval "
            "from 5 to 60 seconds.",
            file=sys.stderr,
        )
        raise SystemExit(1)
