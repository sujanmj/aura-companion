import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore
from runtime.heartbeat import build_runtime_health


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    runtime_health = build_runtime_health(store, user_id)

    print("AURA_RUNTIME_HEALTH")
    for service in runtime_health.get("services", []):
        print(
            f"{service.get('service_name')} | "
            f"{service.get('effective_status')} | "
            f"{service.get('age_seconds')} | "
            f"{service.get('pid')} | "
            f"{service.get('last_seen_at')}"
        )

    summary = runtime_health.get("summary", {})
    print("SUMMARY:")
    print(f"online_count={summary.get('online_count')}")
    print(f"stale_count={summary.get('stale_count')}")
    print(f"missing_count={summary.get('missing_count')}")
    print(f"voice_enabled={summary.get('voice_enabled')}")

    store.close()


if __name__ == "__main__":
    main()
