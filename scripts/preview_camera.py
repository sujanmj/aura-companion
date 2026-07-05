import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from perception.camera import CameraObserver


def main() -> None:
    print("AURA_CAMERA_PREVIEW_START")

    observer = CameraObserver()
    result = observer.capture_preview(seconds=10)

    if result.get("ok"):
        print(result.get("message"))
    else:
        print("AURA_CAMERA_PREVIEW_FAILED")
        print(result.get("message"))
        print(result.get("error"))


if __name__ == "__main__":
    main()
