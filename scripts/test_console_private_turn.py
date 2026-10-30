from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_companion_console as console


class ConsolePrivateTurnTests(unittest.TestCase):
    def test_private_turn_skips_camera_memory_and_feedback_flow(self):
        class Store:
            def apply_schema(self):
                pass

            def get_or_create_user(self, **_kwargs):
                return 1

            def close(self):
                pass

        class Extractor:
            def __init__(self, _store):
                self.saved_messages = []

            def process_user_message(self, user_id, message):
                self.saved_messages.append((user_id, message))

        class Engine:
            def __init__(self, _store, *, use_llm):
                self.use_llm = use_llm

        extractor = Extractor(None)
        prompts = ["n", "n", "y", "/private", "private request", "exit"]
        private_reply = {"response": "Temporary reply", "provider": "local", "tone": "friendly_warm"}

        with (
            patch.object(console, "AuraMemoryStore", Store),
            patch.object(console, "MemoryExtractor", return_value=extractor),
            patch.object(console, "CompanionReactionEngine", Engine),
            patch.object(console, "WindowsTTSSpeaker", lambda **_kwargs: type("SilentSpeaker", (), {"enabled": False})()),
            patch.object(console, "get_default_camera_observer", return_value=object()),
            patch.object(console, "get_observation", side_effect=AssertionError("private turns must skip camera")),
            patch.object(console, "generate_private_response", return_value=private_reply) as private_response,
            patch("builtins.input", side_effect=prompts),
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                console.main(enable_microphone=False)

        private_response.assert_called_once_with("private request", use_llm=False)
        self.assertEqual(extractor.saved_messages, [])
        self.assertIn("AURA (private turn; not saved)", output.getvalue())
        self.assertIn("may receive the message", output.getvalue())


if __name__ == "__main__":
    unittest.main()
