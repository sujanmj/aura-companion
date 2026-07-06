import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    actions = store.get_recent_action_logs(user_id, limit=20)

    print("AURA_RECENT_ACTION_LOGS")
    if not actions:
        print("AURA_RECENT_ACTION_LOGS_NONE")
    else:
        for action in actions:
            target = action.get("target") or "-"
            print(
                f"- {action['id']} | {action['action_type']} | {action.get('status')} | "
                f"{target} | {action.get('created_at')}"
            )
            print(f"  summary={action['action_summary']}")

    store.close()


if __name__ == "__main__":
    main()
