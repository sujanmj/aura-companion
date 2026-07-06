import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from perception.camera import CameraObserver


def print_suggestions(diagnostics: dict) -> None:
    face_count = diagnostics.get("face_count", 0)
    brightness_mean = diagnostics.get("brightness_mean", 0)
    blur_score = diagnostics.get("blur_score", 0)

    print("SUGGESTIONS:")
    if face_count > 0:
        print("- Face detected successfully.")
        return

    if brightness_mean < 45:
        print("- Improve lighting in the room.")
    if blur_score < 40:
        print("- Clean the lens, hold still, and improve focus.")
    if face_count == 0:
        print("- Face the camera directly and move closer.")


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

    diagnostics = result.get("diagnostics") or {}
    print("DIAGNOSTICS:")
    print(f"frame_width: {diagnostics.get('frame_width')}")
    print(f"frame_height: {diagnostics.get('frame_height')}")
    print(f"brightness_mean: {diagnostics.get('brightness_mean')}")
    print(f"blur_score: {diagnostics.get('blur_score')}")
    print(f"face_count: {diagnostics.get('face_count')}")

    if diagnostics:
        print_suggestions(diagnostics)

    print("TIP:")
    print("If no face is detected, run:")
    print("python scripts/preview_camera.py")


if __name__ == "__main__":
    main()
