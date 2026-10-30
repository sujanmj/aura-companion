from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import check_pi_voice_readiness as readiness


class PiVoiceReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.model = Path(self.temp.name) / "vosk-model"
        self.model.mkdir()
        (self.model / "model.conf").write_text("fixture")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inspect(self, **overrides: str):
        environment = {"AURA_VOSK_MODEL_PATH": str(self.model), **overrides}
        return readiness.inspect_readiness(
            environment,
            python_version=(3, 11),
            module_available=lambda _name: True,
            executable_lookup=lambda name: "/usr/bin/espeak-ng" if name == "espeak-ng" else None,
        )

    def test_reports_ready_software_and_keeps_speech_output_optional(self) -> None:
        checks = self.inspect()
        self.assertTrue(all(check.ready for check in checks if check.required))
        self.assertTrue(checks[-1].ready)
        self.assertFalse(checks[-1].required)

    def test_rejects_old_python_and_missing_optional_voice_packages(self) -> None:
        checks = readiness.inspect_readiness(
            {"AURA_VOSK_MODEL_PATH": str(self.model)},
            python_version=(3, 10),
            module_available=lambda _name: False,
            executable_lookup=lambda _name: None,
        )
        self.assertFalse(checks[0].ready)
        self.assertFalse(checks[1].ready)
        self.assertFalse(checks[2].ready)
        self.assertTrue(checks[3].ready)
        self.assertFalse(checks[4].ready)
        self.assertFalse(all(check.ready for check in checks if check.required))

    def test_requires_existing_nonempty_absolute_model_without_symlink_path(self) -> None:
        empty_model = Path(self.temp.name) / "empty"
        empty_model.mkdir()
        relative = readiness.inspect_readiness(
            {"AURA_VOSK_MODEL_PATH": "relative/model"},
            python_version=(3, 11), module_available=lambda _name: True,
        )
        empty = readiness.inspect_readiness(
            {"AURA_VOSK_MODEL_PATH": str(empty_model)},
            python_version=(3, 11), module_available=lambda _name: True,
        )
        self.assertFalse(relative[3].ready)
        self.assertFalse(empty[3].ready)
        if os.name != "nt":
            alias = Path(self.temp.name) / "alias"
            alias.symlink_to(self.model, target_is_directory=True)
            linked = readiness.inspect_readiness(
                {"AURA_VOSK_MODEL_PATH": str(alias)},
                python_version=(3, 11), module_available=lambda _name: True,
            )
            self.assertFalse(linked[3].ready)

    def test_cli_never_prints_model_path_or_claims_hardware_was_tested(self) -> None:
        secret_path = "/private/model/path"
        output = StringIO()
        with (
            patch.dict(os.environ, {"AURA_VOSK_MODEL_PATH": secret_path}),
            redirect_stdout(output),
        ):
            result = readiness.main()
        printed = output.getvalue()
        self.assertEqual(result, 1)
        self.assertNotIn(secret_path, printed)
        self.assertIn("does not open the microphone", printed)
        self.assertIn("AURA_LOCAL_VOICE_SOFTWARE_READY=no", printed)


if __name__ == "__main__":
    unittest.main()
