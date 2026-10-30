from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_companion_console import _confirm_transcript, get_user_message


class BrokenRecognizer:
    def listen_once(self) -> str | None:
        raise OSError("device was disconnected")


class ConsoleVoiceFlowTests(unittest.TestCase):
    def test_retry_device_error_returns_to_typed_input(self):
        with patch("builtins.input", side_effect=["retry", "typed fallback"]) as prompt:
            self.assertEqual(_confirm_transcript(BrokenRecognizer(), "first transcript"), "typed fallback")

        self.assertIn("normal memory/provider flow", prompt.call_args_list[0].args[0])
        self.assertEqual(prompt.call_count, 2)

    def test_initial_device_error_uses_typed_input_without_crashing(self):
        with patch("builtins.input", side_effect=["", "typed fallback"]) as prompt:
            self.assertEqual(get_user_message(BrokenRecognizer(), mic_enabled=True), "typed fallback")

        self.assertEqual(prompt.call_count, 2)

    def test_retry_with_no_speech_uses_typed_input(self):
        class SilentRecognizer:
            def listen_once(self) -> str | None:
                return None

        with patch("builtins.input", side_effect=["retry", "typed fallback"]):
            self.assertEqual(_confirm_transcript(SilentRecognizer(), "first transcript"), "typed fallback")


if __name__ == "__main__":
    unittest.main()
