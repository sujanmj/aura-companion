from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "media" / "snapshots"
PREVIEW_WINDOW_TITLE = "AURA Camera Preview - press q to quit"


class CameraObserver:
    def __init__(self, camera_index: int = 0, snapshot_dir: Path | None = None) -> None:
        self.camera_index = camera_index
        self.snapshot_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR

    def capture_observation(self, save_snapshot: bool = True) -> dict:
        try:
            import cv2
        except ImportError:
            return self._error_result(
                event_summary="OpenCV is not installed.",
                error="opencv_missing",
            )

        camera = None
        try:
            camera = self._open_camera(cv2)
            if camera is None:
                return self._error_result(
                    event_summary="Camera could not be opened.",
                    error="camera_unavailable",
                )

            for _ in range(5):
                camera.read()

            success, frame = camera.read()
            if not success or frame is None:
                return self._error_result(
                    event_summary="Camera frame capture failed.",
                    error="capture_failed",
                )

            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_detector = cv2.CascadeClassifier(cascade_path)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(60, 60),
            )

            face_count = len(faces)
            frame_height, frame_width = gray.shape[:2]
            brightness_mean = float(gray.mean())
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            diagnostics = {
                "frame_width": int(frame_width),
                "frame_height": int(frame_height),
                "brightness_mean": round(brightness_mean, 2),
                "blur_score": round(blur_score, 2),
                "face_count": face_count,
            }

            event_type = "visual_context"
            event_summary = self._build_event_summary(face_count, brightness_mean, blur_score)
            confidence = 0.75 if face_count > 0 else 0.4

            snapshot_path: str | None = None
            if save_snapshot:
                snapshot_frame = frame.copy()
                if face_count > 0:
                    for x, y, width, height in faces:
                        cv2.rectangle(
                            snapshot_frame,
                            (x, y),
                            (x + width, y + height),
                            (0, 255, 0),
                            2,
                        )
                self.snapshot_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                snapshot_file = self.snapshot_dir / f"aura_camera_{timestamp}.jpg"
                cv2.imwrite(str(snapshot_file), snapshot_frame)
                snapshot_path = str(snapshot_file)

            return {
                "ok": True,
                "event_type": event_type,
                "event_summary": event_summary,
                "confidence": confidence,
                "snapshot_path": snapshot_path,
                "diagnostics": diagnostics,
                "error": None,
            }
        except Exception as exc:
            return self._error_result(
                event_summary="Camera observation failed.",
                error=str(exc),
            )
        finally:
            if camera is not None:
                camera.release()

    def capture_preview(self, seconds: int = 10) -> dict:
        try:
            import cv2
        except ImportError:
            return {
                "ok": False,
                "message": "OpenCV is not installed.",
                "error": "opencv_missing",
            }

        camera = None
        try:
            camera = self._open_camera(cv2)
            if camera is None:
                return {
                    "ok": False,
                    "message": "Camera could not be opened.",
                    "error": "camera_unavailable",
                }

            start = time.time()
            while time.time() - start < seconds:
                success, frame = camera.read()
                if not success or frame is None:
                    return {
                        "ok": False,
                        "message": "Camera frame capture failed during preview.",
                        "error": "capture_failed",
                    }

                cv2.imshow(PREVIEW_WINDOW_TITLE, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            return {"ok": True, "message": "Preview completed"}
        except Exception as exc:
            return {
                "ok": False,
                "message": "Preview failed.",
                "error": str(exc),
            }
        finally:
            if camera is not None:
                camera.release()
            try:
                import cv2

                cv2.destroyAllWindows()
            except ImportError:
                pass

    def _open_camera(self, cv2: object):
        camera = cv2.VideoCapture(self.camera_index)
        if not camera.isOpened():
            camera.release()
            return None

        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return camera

    @staticmethod
    def _build_event_summary(face_count: int, brightness_mean: float, blur_score: float) -> str:
        if face_count > 0:
            return "User appears present near the camera."
        if brightness_mean < 45:
            return "Camera is working, but the room looks too dark for reliable face detection."
        if blur_score < 40:
            return "Camera is working, but the image looks blurry for reliable face detection."
        return "Camera is working, but no clear face was detected."

    @staticmethod
    def _error_result(event_summary: str, error: str) -> dict:
        return {
            "ok": False,
            "event_type": "camera_error",
            "event_summary": event_summary,
            "confidence": 0.0,
            "snapshot_path": None,
            "error": error,
        }


def get_default_camera_observer() -> CameraObserver:
    return CameraObserver()
