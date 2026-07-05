import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore
from perception.camera import CameraObserver


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    observer = CameraObserver()
    result = observer.capture_observation()

    if not result.get("ok"):
        print("AURA_CAMERA_OBSERVATION_FAILED")
        print(result.get("error"))
        store.close()
        return

    observation_id = store.add_observation(
        user_id,
        event_type=result["event_type"],
        event_summary=result["event_summary"],
        confidence=float(result["confidence"]),
        source="camera",
    )

    store.close()

    print("AURA_CAMERA_OBSERVATION_CAPTURED")
    print(f"observation_id={observation_id}")
    print(f"summary={result['event_summary']}")
    print(f"snapshot={result.get('snapshot_path')}")


if __name__ == "__main__":
    main()
