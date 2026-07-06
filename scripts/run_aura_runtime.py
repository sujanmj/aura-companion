from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STOP_TIMEOUT_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.5

SERVICE_DEFINITIONS: tuple[dict[str, str], ...] = (
    {"name": "sensor_api", "script": "scripts/run_sensor_api.py"},
    {"name": "live_safety_monitor", "script": "scripts/run_live_safety_monitor.py"},
    {"name": "confirmation_timeout_watcher", "script": "scripts/run_confirmation_timeout_watcher.py"},
)

DASHBOARD_URL = "http://127.0.0.1:8787/dashboard"
HEALTH_URL = "http://127.0.0.1:8787/health"


def get_service_script_path(project_root: Path, script: str) -> Path:
    return (project_root / script).resolve()


def build_service_commands(
    project_root: Path,
    *,
    include_api: bool = True,
    include_monitor: bool = True,
    include_timeout_watcher: bool = True,
) -> list[dict[str, str]]:
    flags = {
        "sensor_api": include_api,
        "live_safety_monitor": include_monitor,
        "confirmation_timeout_watcher": include_timeout_watcher,
    }
    commands: list[dict[str, str]] = []
    for service in SERVICE_DEFINITIONS:
        if not flags.get(service["name"], True):
            continue
        script_path = get_service_script_path(project_root, service["script"])
        commands.append(
            {
                "name": service["name"],
                "script": service["script"],
                "path": str(script_path),
            }
        )
    return commands


def start_service(
    python_executable: str,
    project_root: Path,
    service: dict[str, str],
) -> subprocess.Popen:
    return subprocess.Popen(
        [python_executable, service["path"]],
        cwd=str(project_root),
    )


def stop_service(name: str, process: subprocess.Popen, timeout: int = STOP_TIMEOUT_SECONDS) -> None:
    if process.poll() is not None:
        print(f"AURA_RUNTIME_SERVICE_STOPPED name={name}")
        return

    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

    print(f"AURA_RUNTIME_SERVICE_STOPPED name={name}")


def stop_all_services(
    processes: list[tuple[str, subprocess.Popen]],
    timeout: int = STOP_TIMEOUT_SECONDS,
) -> None:
    for name, process in processes:
        stop_service(name, process, timeout=timeout)


def run_runtime(
    python_executable: str,
    project_root: Path,
    *,
    include_api: bool = True,
    include_monitor: bool = True,
    include_timeout_watcher: bool = True,
) -> int:
    services = build_service_commands(
        project_root,
        include_api=include_api,
        include_monitor=include_monitor,
        include_timeout_watcher=include_timeout_watcher,
    )

    if not services:
        print("AURA_RUNTIME_ERROR: no services selected")
        return 1

    print("AURA_RUNTIME_STARTING")

    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        for service in services:
            process = start_service(python_executable, project_root, service)
            processes.append((service["name"], process))
            print(f"AURA_RUNTIME_SERVICE_STARTED name={service['name']} pid={process.pid}")

        print(f"Dashboard: {DASHBOARD_URL}")
        print(f"Health: {HEALTH_URL}")

        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"AURA_RUNTIME_SERVICE_EXITED name={name} code={return_code}")
                    print("AURA_RUNTIME_STOPPING")
                    stop_all_services(processes)
                    print("AURA_RUNTIME_STOPPED")
                    return 1
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nAURA_RUNTIME_STOPPING")
        stop_all_services(processes)
        print("AURA_RUNTIME_STOPPED")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AURA local runtime services.")
    parser.add_argument("--no-api", action="store_true", help="Do not start sensor API / dashboard")
    parser.add_argument("--no-monitor", action="store_true", help="Do not start live safety monitor")
    parser.add_argument(
        "--no-timeout-watcher",
        action="store_true",
        help="Do not start confirmation timeout watcher",
    )
    args = parser.parse_args()

    exit_code = run_runtime(
        sys.executable,
        PROJECT_ROOT,
        include_api=not args.no_api,
        include_monitor=not args.no_monitor,
        include_timeout_watcher=not args.no_timeout_watcher,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
