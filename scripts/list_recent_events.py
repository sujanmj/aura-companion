import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    events = store.get_recent_device_events(user_id, limit=20)

    print("AURA_RECENT_DEVICE_EVENTS")
    if not events:
        print("AURA_RECENT_DEVICE_EVENTS_NONE")
    else:
        for event in events:
            room = event.get("room") or "-"
            source = event.get("source") or "-"
            requires_action = bool(event.get("requires_action"))
            print(
                f"- {event['id']} | {event['event_type']} | {event.get('severity')} | "
                f"{room} | {source} | requires_action={requires_action} | "
                f"status={event.get('action_status') or 'none'} | {event.get('created_at')}"
            )
            print(f"  summary={event['event_summary']}")

    store.close()


if __name__ == "__main__":
    main()
