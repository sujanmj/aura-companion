from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from config.env_loader import load_env_file


class BaseSpeaker:
    def speak(self, text: str) -> bool:
        raise NotImplementedError


def list_windows_voices() -> list[str]:
    script = (
        "Add-Type -AssemblyName System.Speech\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }\n"
    )

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            error_output = (result.stderr or result.stdout or "unknown error").strip()
            print(f"AURA_TTS_VOICE_LIST_ERROR: {error_output}")
            return []

        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as exc:
        print(f"AURA_TTS_VOICE_LIST_ERROR: {exc}")
        return []


def _escape_ps_single_quote(text: str) -> str:
    return text.replace("'", "''")


def _resolve_windows_voice(explicit_voice: str | None = None) -> str | None:
    if explicit_voice:
        return explicit_voice

    env_voice = os.environ.get("AURA_WINDOWS_VOICE")
    if env_voice:
        return env_voice

    for name in list_windows_voices():
        if "zira" in name.lower():
            return name

    return None


def get_selected_windows_voice(voice_name: str | None = None) -> str | None:
    load_env_file()
    return _resolve_windows_voice(voice_name)


class WindowsTTSSpeaker(BaseSpeaker):
    def __init__(
        self,
        enabled: bool = True,
        rate: int = 0,
        volume: int = 90,
        voice_name: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.rate = rate
        self.volume = volume
        self.voice_name = voice_name if voice_name is not None else os.environ.get("AURA_WINDOWS_VOICE")

    def speak(self, text: str) -> bool:
        if not self.enabled:
            return False

        cleaned = text.strip()
        if not cleaned:
            return False

        script_path: Path | None = None
        try:
            load_env_file()
            selected_voice = _resolve_windows_voice(self.voice_name)
            safe_text = self._sanitize_for_here_string(cleaned)
            voice_block = ""
            if selected_voice:
                safe_voice = _escape_ps_single_quote(selected_voice)
                voice_block = (
                    f"try {{\n"
                    f"    $speaker.SelectVoice('{safe_voice}')\n"
                    f"}} catch {{\n"
                    f"    # Use default voice if selection fails.\n"
                    f"}}\n"
                )

            script_content = (
                "Add-Type -AssemblyName System.Speech\n"
                "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
                f"{voice_block}"
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
