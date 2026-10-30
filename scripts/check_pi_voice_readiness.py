"""Check installed local-voice prerequisites without activating any hardware."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import NamedTuple


class Check(NamedTuple):
    name: str
    ready: bool
    detail: str
    required: bool = True


def _model_directory_ready(raw_path: str) -> bool:
    """Accept an installed non-symlinked model directory with content."""
    try:
        path = Path(raw_path).expanduser()
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            return False
        return next(path.iterdir(), None) is not None
    except (OSError, RuntimeError, ValueError):
        return False


def inspect_readiness(
    environment: Mapping[str, str] | None = None,
    *,
    python_version: tuple[int, int] | None = None,
    module_available: Callable[[str], bool] | None = None,
    executable_lookup: Callable[[str], str | None] | None = None,
) -> tuple[Check, ...]:
    """Inspect software prerequisites; never import providers or touch devices."""
    values = os.environ if environment is None else environment
    version = python_version or (sys.version_info.major, sys.version_info.minor)

    def has_module(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError, AttributeError):
            return False

    find_module = module_available or has_module
    find_executable = executable_lookup or shutil.which
    model_path = values.get("AURA_VOSK_MODEL_PATH", "")
    model_ready = _model_directory_ready(model_path) if model_path else False

    vosk_available = find_module("vosk")
    audio_available = find_module("sounddevice")
    espeak_available = find_executable("espeak-ng") is not None

    return (
        Check(
            "Python runtime",
            version >= (3, 11),
            "Python 3.11 or newer is installed" if version >= (3, 11)
            else "install Python 3.11 or newer",
        ),
        Check(
            "Vosk speech package",
            vosk_available,
            "installed" if vosk_available else "install requirements-pi-voice.txt",
        ),
        Check(
            "Audio input package",
            audio_available,
            "installed" if audio_available else "install requirements-pi-voice.txt",
        ),
        Check(
            "Local Vosk model",
            model_ready,
            "configured model directory is present" if model_ready
            else "set AURA_VOSK_MODEL_PATH to an installed, non-empty absolute model directory",
        ),
        Check(
            "Offline speech output",
            espeak_available,
            "espeak-ng is installed" if espeak_available
            else "optional: install espeak-ng for offline spoken replies",
            required=False,
        ),
    )


def main() -> int:
    checks = inspect_readiness()
    print("AURA local voice software readiness")
    for check in checks:
        state = "ready" if check.ready else "missing"
        if not check.required and not check.ready:
            state = "optional"
        print(f"[{state}] {check.name}: {check.detail}")

    ready = all(check.ready for check in checks if check.required)
    print(f"AURA_LOCAL_VOICE_SOFTWARE_READY={'yes' if ready else 'no'}")
    print(
        "This check does not open the microphone, test permissions, inspect audio hardware, "
        "or measure model accuracy."
    )
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
