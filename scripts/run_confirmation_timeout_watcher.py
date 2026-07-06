import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore
from monitor.confirmation_timeout_watcher import ConfirmationTimeoutWatcher


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AURA confirmation timeout watcher.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process due confirmations once and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Polling interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum confirmations per cycle (default: 20)",
    )
    args = parser.parse_args()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    watcher = ConfirmationTimeoutWatcher(store, interval_seconds=args.interval)

    if args.once:
        watcher.process_once(user_id, limit=args.limit)
        print("AURA_CONFIRMATION_TIMEOUT_WATCHER_ONCE_OK")
        store.close()
        return

    try:
        watcher.run_forever(user_id, interval_seconds=args.interval, limit=args.limit)
    finally:
        store.close()


if __name__ == "__main__":
    main()
