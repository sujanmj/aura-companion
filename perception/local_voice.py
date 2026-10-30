"""Explicit push-to-talk, on-device speech recognition for Linux/Pi and macOS.

The optional audio and Vosk packages are imported only when this recognizer is
constructed. It never downloads a model or writes microphone audio to disk.
"""
from __future__ import annotations

import json
import os
import queue
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


class LocalSpeechRecognizer:
    """Transcribe one explicitly requested utterance with a local Vosk model."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        sample_rate: int = 16_000,
        max_seconds: float = 15.0,
        model_factory: Callable[[str], Any] | None = None,
        recognizer_factory: Callable[[Any, int], Any] | None = None,
        stream_factory: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        configured_path = model_path if model_path is not None else os.environ.get("AURA_VOSK_MODEL_PATH", "")
        if not str(configured_path).strip():
            raise ValueError("set AURA_VOSK_MODEL_PATH to an installed local model directory")
        self.model_path = Path(configured_path).expanduser()
        if not self.model_path.is_absolute() or not self.model_path.is_dir():
            raise ValueError("AURA_VOSK_MODEL_PATH must name an existing absolute model directory")
        if sample_rate != 16_000:
            raise ValueError("the configured Vosk model requires 16000 Hz audio")
        if not 1 <= max_seconds <= 30:
            raise ValueError("maximum utterance duration must be between 1 and 30 seconds")

        if model_factory is None or recognizer_factory is None:
            try:
                from vosk import Model, KaldiRecognizer  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError("install the optional Pi voice dependencies to use local speech") from exc
            model_factory = model_factory or Model
            recognizer_factory = recognizer_factory or KaldiRecognizer
        if stream_factory is None:
            try:
                import sounddevice as sd  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError("install the optional Pi voice dependencies to use local speech") from exc
            stream_factory = sd.RawInputStream

        self.sample_rate = sample_rate
        self.max_seconds = max_seconds
        self._clock = clock
        self._stream_factory = stream_factory
        self._model = model_factory(str(self.model_path))
        self._recognizer_factory = recognizer_factory

    @staticmethod
    def _text(result: str) -> str:
        try:
            payload = json.loads(result)
        except (TypeError, json.JSONDecodeError):
            return ""
        text = payload.get("text", "") if isinstance(payload, dict) else ""
        return text.strip() if isinstance(text, str) else ""

    def listen_once(self) -> str | None:
        """Open the microphone for one bounded utterance and always close it."""
        audio: queue.Queue[bytes] = queue.Queue(maxsize=16)
        recognizer = self._recognizer_factory(self._model, self.sample_rate)

        def on_audio(indata: Any, _frames: int, _time_info: Any, _status: Any) -> None:
            block = bytes(indata)
            try:
                audio.put_nowait(block)
            except queue.Full:
                # Prefer recent speech over stale queued audio; no audio is persisted.
                try:
                    audio.get_nowait()
                except queue.Empty:
                    pass
                try:
                    audio.put_nowait(block)
                except queue.Full:
                    pass

        stream = self._stream_factory(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=4_000,
            callback=on_audio,
        )
        deadline = self._clock() + self.max_seconds
        started = False
        try:
            stream.start()
            started = True
            while self._clock() < deadline:
                try:
                    block = audio.get(timeout=min(0.25, max(0.01, deadline - self._clock())))
                except queue.Empty:
                    continue
                if recognizer.AcceptWaveform(block):
                    return self._text(recognizer.Result())[:1000] or None
            return self._text(recognizer.FinalResult())[:1000] or None
        finally:
            try:
                if started:
                    stream.stop()
            finally:
                stream.close()


def get_default_local_recognizer() -> LocalSpeechRecognizer:
    """Create the optional local recognizer from the explicit model setting."""
    return LocalSpeechRecognizer()
