"""Fail closed before a network-exposed Pi sensor API starts."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from config.sensor_transport import is_regular_nonsymlink_file
from collections.abc import Mapping


def validate_environment(environment: Mapping[str, str] | None = None) -> bool:
    values = os.environ if environment is None else environment
    token = values.get("AURA_SENSOR_API_TOKEN", "")
    db_path = values.get("AURA_DB_PATH", "")
    try:
        cert_file = Path(values.get("AURA_SENSOR_TLS_CERT_FILE", ""))
        key_file = Path(values.get("AURA_SENSOR_TLS_KEY_FILE", ""))
        certificate_ready = is_regular_nonsymlink_file(cert_file)
        key_ready = is_regular_nonsymlink_file(key_file)
        key_mode = key_file.stat().st_mode if key_ready else 0
    except OSError:
        certificate_ready = key_ready = False
        key_mode = 0
    return (
        len(token) >= 32
        and token.strip() == token
        and len(set(token)) > 1
        and db_path == "/var/lib/aura/aura_memory.db"
        and certificate_ready
        and key_ready
        and key_mode & 0o027 == 0
    )


if __name__ == "__main__":
    if not validate_environment():
        print(
            "AURA Pi service configuration invalid: set a unique sensor API token "
            "of at least 32 characters, TLS certificate/key files readable by the "
            "service account, and the service database path.",
            file=sys.stderr,
        )
        raise SystemExit(1)
