from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class WindowsSpeechRecognizer:
    def __init__(self, timeout_seconds: int = 8) -> None:
        self.timeout_seconds = timeout_seconds

    def listen_once(self) -> str | None:
        script_path: Path | None = None
        try:
            script_content = (
                "Add-Type -AssemblyName System.Speech\n"
                "$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine\n"
                "$recognizer.SetInputToDefaultAudioDevice()\n"
                "$grammar = New-Object System.Speech.Recognition.DictationGrammar\n"
                "$recognizer.LoadGrammar($grammar)\n"
                f"$result = $recognizer.Recognize([TimeSpan]::FromSeconds({int(self.timeout_seconds)}))\n"
                "if ($result -ne $null) {\n"
                "    Write-Output $result.Text\n"
                "}\n"
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
                timeout=self.timeout_seconds + 15,
            )

            if result.returncode != 0:
                error_output = (result.stderr or result.stdout or "unknown error").strip()
                if error_output:
                    print(f"AURA_STT_ERROR: {error_output}")
                return None

            text = result.stdout.strip()
            return text if text else None
        except subprocess.TimeoutExpired:
            print("AURA_STT_ERROR: recognition timed out")
            return None
        except Exception as exc:
            print(f"AURA_STT_ERROR: {exc}")
            return None
        finally:
            if script_path is not None and script_path.exists():
                try:
                    script_path.unlink()
                except OSError:
                    pass


def get_default_recognizer() -> WindowsSpeechRecognizer:
    return WindowsSpeechRecognizer()
