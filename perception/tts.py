from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from config.env_loader import load_env_file


class BaseSpeaker:
    def speak(self, text: str) -> bool:
        raise NotImplementedError


class WindowsTTSSpeaker(BaseSpeaker):
    def __init__(self, enabled: bool = True, rate: int = 0, volume: int = 90) -> None:
        self.enabled = enabled
        self.rate = rate
        self.volume = volume

    def speak(self, text: str) -> bool:
        if not self.enabled:
            return False

        cleaned = text.strip()
        if not cleaned:
            return False

        script_path: Path | None = None
        try:
            safe_text = self._sanitize_for_here_string(cleaned)
            script_content = (
                "Add-Type -AssemblyName System.Speech\n"
                "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
                f"$speaker.Rate = {int(self.rate)}\n"
                f"$speaker.Volume = {int(self.volume)}\n"
                "$text = @'\n"
                f"{safe_text}\n"
                "'@\n"
                "$speaker.Speak($text)\n"
            )

            with tempfile.NamedTemporaryFile(delete=False, suffix=".ps1", mode="w", encoding="utf-8") as handle:
                handle.write(script_content)
                script_path = Path(handle.name)

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return True

            error_output = (result.stderr or result.stdout or "unknown error").strip()
            print(f"AURA_TTS_ERROR: {error_output}")
            return False
        except Exception as exc:
            print(f"AURA_TTS_ERROR: {exc}")
            return False
        finally:
            if script_path is not None and script_path.exists():
                try:
                    script_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _sanitize_for_here_string(text: str) -> str:
        cleaned = text.replace("\x00", "")
        lines = cleaned.splitlines()
        safe_lines: list[str] = []
        for line in lines:
            if line.strip() == "'@":
                safe_lines.append(" ")
            else:
                safe_lines.append(line)
        return "\n".join(safe_lines)


def get_speaker_from_env() -> BaseSpeaker:
    load_env_file()
    provider = os.environ.get("AURA_TTS_PROVIDER", "windows").lower()
    if provider != "windows":
        print(f"AURA_TTS_INFO: provider '{provider}' is disabled; using windows.")
    return WindowsTTSSpeaker(enabled=True)


def get_default_speaker() -> WindowsTTSSpeaker:
    return WindowsTTSSpeaker()
