from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from perception.tts import EspeakNGSpeaker, get_speaker_from_env


class Result:
    def __init__(self, returncode=0):
        self.returncode = returncode


class LocalTTSTests(unittest.TestCase):
    def test_enabled_local_output_passes_text_over_stdin_without_shell(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return Result()

        speaker = EspeakNGSpeaker(runner=runner)
        self.assertTrue(speaker.speak("hello $(touch /tmp/not-run)"))
        command, kwargs = calls[0]
        self.assertEqual(command, ["espeak-ng", "--stdin"])
        self.assertEqual(kwargs["input"], "hello $(touch /tmp/not-run)")
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])

    def test_disabled_or_blank_output_does_not_call_speech_binary(self):
        def unexpected_call(*_args, **_kwargs):
            self.fail("disabled speech should not invoke espeak-ng")

        speaker = EspeakNGSpeaker(enabled=False, runner=unexpected_call)
        self.assertFalse(speaker.speak("hello"))
        speaker.enabled = True
        self.assertFalse(speaker.speak("  \x00  "))

    def test_oversized_output_is_rejected_before_launch(self):
        def unexpected_call(*_args, **_kwargs):
            self.fail("oversized speech should not invoke espeak-ng")

        self.assertFalse(EspeakNGSpeaker(runner=unexpected_call).speak("a" * 8_001))

    def test_missing_binary_timeout_and_nonzero_exit_fail_closed(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("espeak-ng", 1), OSError()):
            with self.subTest(error=type(error).__name__):
                def fail(*_args, error=error, **_kwargs):
                    raise error
                self.assertFalse(EspeakNGSpeaker(runner=fail).speak("hello"))

        self.assertFalse(EspeakNGSpeaker(runner=lambda *_args, **_kwargs: Result(1)).speak("hello"))

    def test_voice_provider_requires_explicit_configuration(self):
        with patch.dict(os.environ, {"AURA_TTS_PROVIDER": "espeak-ng"}, clear=False):
            speaker = get_speaker_from_env()
        self.assertIsInstance(speaker, EspeakNGSpeaker)


if __name__ == "__main__":
    unittest.main()
