import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from actions.voice_runtime import create_runtime_speaker
from memory.sqlite_store import AuraMemoryStore
from monitor.live_safety_monitor import LiveSafetyMonitor


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AURA live safety monitor.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending events once and exit",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3,
        help="Polling interval in seconds (default: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum pending events per cycle (default: 10)",
    )
    args = parser.parse_args()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    speaker = create_runtime_speaker()
    monitor = LiveSafetyMonitor(store, speaker=speaker)

    if args.once:
        results = monitor.process_once(user_id, limit=args.limit)
        for result in results:
            print(
                f"- event_id={result['event_id']} "
                f"type={result['event_type']} status={result['status']}"
            )
        print("AURA_LIVE_SAFETY_MONITOR_ONCE_OK")
        store.close()
        return

    try:
        monitor.run_forever(user_id, interval_seconds=args.interval, limit=args.limit)
    finally:
        store.close()


if __name__ == "__main__":
    main()
