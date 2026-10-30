from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_companion_console import get_observation


class FakeStore:
    def __init__(self):
        self.observations = []

    def add_observation(self, user_id, **observation):
        self.observations.append((user_id, observation))


class FakeCamera:
    def __init__(self, result):
        self.result = result
        self.save_snapshot = None

    def capture_observation(self, save_snapshot=True):
        self.save_snapshot = save_snapshot
        return self.result


class ConsoleObservationPrivacyTests(unittest.TestCase):
    def test_camera_capture_saves_only_derived_summary_by_default(self):
        store = FakeStore()
        camera = FakeCamera({
            "ok": True,
            "event_type": "visual_context",
            "event_summary": "Camera is working, but no clear face was detected.",
            "confidence": 0.4,
        })
        with patch("builtins.input", return_value=""):
            observation = get_observation(store, 5, True, camera)

        self.assertFalse(camera.save_snapshot)
        self.assertEqual(observation, camera.result["event_summary"])
        self.assertEqual(len(store.observations), 1)
        self.assertEqual(store.observations[0][0], 5)
        self.assertEqual(store.observations[0][1]["source"], "camera")
        self.assertEqual(store.observations[0][1]["event_summary"], observation)

    def test_camera_failure_falls_back_to_typed_observation_without_saving_image(self):
        store = FakeStore()
        camera = FakeCamera({"ok": False, "event_summary": "Camera unavailable."})
        with patch("builtins.input", side_effect=["", "manual note"]):
            observation = get_observation(store, 5, True, camera)

        self.assertFalse(camera.save_snapshot)
        self.assertEqual(observation, "manual note")
        self.assertEqual(store.observations[0][1]["source"], "console")


if __name__ == "__main__":
    unittest.main()
