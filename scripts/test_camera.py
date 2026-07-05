import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from perception.camera import CameraObserver


def main() -> None:
    print("AURA_CAMERA_TEST_START")

    observer = CameraObserver()
    result = observer.capture_observation()

    if result.get("ok"):
        print("AURA_CAMERA_TEST_OK")
    else:
        print("AURA_CAMERA_TEST_FAILED")

    print("EVENT TYPE:")
    print(result.get("event_type"))
    print("EVENT SUMMARY:")
    print(result.get("event_summary"))
    print("CONFIDENCE:")
    print(result.get("confidence"))
    print("SNAPSHOT:")
    print(result.get("snapshot_path"))
    print("ERROR:")
    print(result.get("error"))
    print("TIP:")
    print("If no face is detected, run:")
    print("python scripts/preview_camera.py")


if __name__ == "__main__":
    main()
