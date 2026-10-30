from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from perception.local_voice import LocalSpeechRecognizer
from scripts.run_companion_console import _build_speech_recognizer


class FakeRecognizer:
    def __init__(self, *, accept: bool = True, result: str = "hello aura"):
        self.accept = accept
        self.result = result
        self.accepted_blocks: list[bytes] = []

    def AcceptWaveform(self, block: bytes) -> bool:
        self.accepted_blocks.append(block)
        return self.accept

    def Result(self) -> str:
        return json.dumps({"text": self.result})

    def FinalResult(self) -> str:
        return json.dumps({"text": self.result})


class FakeStream:
    def __init__(self, callback, *, error: Exception | None = None, **_kwargs):
        self.callback = callback
        self.error = error
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        self.started = True
        if self.error:
            raise self.error
        self.callback(b"volatile pcm", 1, None, None)

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeClock:
    def __init__(self):
        self.current = 0.0

    def __call__(self):
        self.current += 0.4
        return self.current


class LocalVoiceTests(unittest.TestCase):
    def test_disabled_microphone_does_not_construct_a_recognizer(self):
        with patch("perception.local_voice.get_default_local_recognizer") as factory:
            self.assertIsNone(_build_speech_recognizer(False))
            factory.assert_not_called()

    def make_recognizer(self, directory: Path, speech: FakeRecognizer, streams: list[FakeStream]):
        def stream_factory(**kwargs):
            stream = FakeStream(kwargs.pop("callback"), **kwargs)
            streams.append(stream)
            return stream

        return LocalSpeechRecognizer(
            directory,
            model_factory=lambda _path: object(),
            recognizer_factory=lambda _model, _rate: speech,
            stream_factory=stream_factory,
            max_seconds=1,
        )

    def test_model_path_must_be_explicit_existing_and_absolute(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "existing absolute"):
                LocalSpeechRecognizer(Path(directory) / "missing", model_factory=lambda _: None,
                                      recognizer_factory=lambda *_: None, stream_factory=lambda **_: None)
            with self.assertRaisesRegex(ValueError, "absolute"):
                LocalSpeechRecognizer("relative-model", model_factory=lambda _: None,
                                      recognizer_factory=lambda *_: None, stream_factory=lambda **_: None)

    def test_microphone_opens_only_for_one_explicit_bounded_utterance_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            streams: list[FakeStream] = []
            speech = FakeRecognizer()
            recognizer = self.make_recognizer(Path(directory), speech, streams)
            self.assertEqual(streams, [])

            self.assertEqual(recognizer.listen_once(), "hello aura")
            self.assertEqual(len(streams), 1)
            self.assertTrue(streams[0].started)
            self.assertTrue(streams[0].stopped)
            self.assertTrue(streams[0].closed)
            self.assertEqual(speech.accepted_blocks, [b"volatile pcm"])

    def test_empty_speech_returns_none_and_closes_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            streams: list[FakeStream] = []
            recognizer = self.make_recognizer(Path(directory), FakeRecognizer(result=""), streams)
            self.assertIsNone(recognizer.listen_once())
            self.assertTrue(streams[0].stopped)
            self.assertTrue(streams[0].closed)

    def test_capture_error_still_closes_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            streams: list[FakeStream] = []

            def stream_factory(**kwargs):
                stream = FakeStream(kwargs.pop("callback"), error=OSError("device unavailable"), **kwargs)
                streams.append(stream)
                return stream

            recognizer = LocalSpeechRecognizer(
                directory,
                model_factory=lambda _path: object(),
                recognizer_factory=lambda *_: FakeRecognizer(),
                stream_factory=stream_factory,
            )
            with self.assertRaisesRegex(OSError, "device unavailable"):
                recognizer.listen_once()
            self.assertTrue(streams[0].closed)
            self.assertFalse(streams[0].stopped)

    def test_silence_stops_after_the_configured_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            class SilentStream(FakeStream):
                def start(self):
                    self.started = True

            streams = []

            def stream_factory(**kwargs):
                stream = SilentStream(kwargs.pop("callback"), **kwargs)
                streams.append(stream)
                return stream

            speech = FakeRecognizer(result="")
            recognizer = LocalSpeechRecognizer(
                directory,
                max_seconds=1,
                model_factory=lambda _path: object(),
                recognizer_factory=lambda *_: speech,
                stream_factory=stream_factory,
                clock=FakeClock(),
            )
            self.assertIsNone(recognizer.listen_once())
            self.assertTrue(streams[0].stopped)
            self.assertTrue(streams[0].closed)
            self.assertEqual(speech.accepted_blocks, [])


if __name__ == "__main__":
    unittest.main()
