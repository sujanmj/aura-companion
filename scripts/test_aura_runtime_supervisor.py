import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_aura_runtime import (
    SERVICE_DEFINITIONS,
    build_service_commands,
    get_service_script_path,
)

EXPECTED_NAMES = {
    "sensor_api",
    "live_safety_monitor",
    "confirmation_timeout_watcher",
}


def main() -> None:
    defined_names = {service["name"] for service in SERVICE_DEFINITIONS}
    if defined_names != EXPECTED_NAMES:
        print("AURA_RUNTIME_SUPERVISOR_TEST_ERROR: unexpected service names")
        raise SystemExit(1)

    commands = build_service_commands(PROJECT_ROOT)
    if len(commands) != len(SERVICE_DEFINITIONS):
        print("AURA_RUNTIME_SUPERVISOR_TEST_ERROR: default service command count mismatch")
        raise SystemExit(1)

    for service in SERVICE_DEFINITIONS:
        script_path = get_service_script_path(PROJECT_ROOT, service["script"])
        if not script_path.is_file():
            print(f"AURA_RUNTIME_SUPERVISOR_TEST_ERROR: missing script {service['script']}")
            raise SystemExit(1)

    command_names = {command["name"] for command in commands}
    if command_names != EXPECTED_NAMES:
        print("AURA_RUNTIME_SUPERVISOR_TEST_ERROR: built command names mismatch")
        raise SystemExit(1)

    for command in commands:
        if not Path(command["path"]).is_file():
            print(f"AURA_RUNTIME_SUPERVISOR_TEST_ERROR: missing path {command['path']}")
            raise SystemExit(1)

    partial = build_service_commands(PROJECT_ROOT, include_api=False)
    if any(item["name"] == "sensor_api" for item in partial):
        print("AURA_RUNTIME_SUPERVISOR_TEST_ERROR: --no-api filter failed")
        raise SystemExit(1)

    print("AURA_RUNTIME_SUPERVISOR_TEST_OK")


if __name__ == "__main__":
    main()
