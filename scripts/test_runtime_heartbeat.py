import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore
from runtime.heartbeat import RuntimeHeartbeat, build_runtime_health


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    heartbeat = RuntimeHeartbeat(store, user_id)
    heartbeat.beat("sensor_api", metadata={"host": "127.0.0.1", "port": 8787})
    heartbeat.beat("live_safety_monitor")

    runtime_health = build_runtime_health(store, user_id)
    services = runtime_health.get("services", [])
    service_by_name = {service.get("service_name"): service for service in services}

    if "sensor_api" not in service_by_name:
        print("AURA_RUNTIME_HEARTBEAT_TEST_ERROR: sensor_api missing")
        raise SystemExit(1)

    if "live_safety_monitor" not in service_by_name:
        print("AURA_RUNTIME_HEARTBEAT_TEST_ERROR: live_safety_monitor missing")
        raise SystemExit(1)

    if service_by_name["sensor_api"].get("effective_status") != "online":
        print("AURA_RUNTIME_HEARTBEAT_TEST_ERROR: sensor_api not online")
        raise SystemExit(1)

    if service_by_name["live_safety_monitor"].get("effective_status") != "online":
        print("AURA_RUNTIME_HEARTBEAT_TEST_ERROR: live_safety_monitor not online")
        raise SystemExit(1)

    timeout_watcher = service_by_name.get("confirmation_timeout_watcher")
    if timeout_watcher is None or timeout_watcher.get("effective_status") != "missing":
        print("AURA_RUNTIME_HEARTBEAT_TEST_ERROR: expected confirmation_timeout_watcher missing")
        raise SystemExit(1)

    print("RUNTIME HEALTH:")
    for service in services:
        print(
            f"- {service.get('service_name')} | "
            f"effective_status={service.get('effective_status')} | "
            f"age_seconds={service.get('age_seconds')} | "
            f"pid={service.get('pid')}"
        )

    store.close()
    print("AURA_RUNTIME_HEARTBEAT_TEST_OK")


if __name__ == "__main__":
    main()
