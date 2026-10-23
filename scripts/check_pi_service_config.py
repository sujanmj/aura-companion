"""Fail closed before a network-exposed Pi sensor API starts."""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping


def validate_environment(environment: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environment is None else environment
    token = values.get("AURA_SENSOR_API_TOKEN", "")
    db_path = values.get("AURA_DB_PATH", "")
    return (
        len(token) >= 32
        and token.strip() == token
        and len(set(token)) > 1
        and db_path == "/var/lib/aura/aura_memory.db"
    )


if __name__ == "__main__":
    if not validate_environment():
        print(
            "AURA Pi service configuration invalid: set a unique sensor API token "
            "of at least 32 characters and use the service database path.",
            file=sys.stderr,
        )
        raise SystemExit(1)
