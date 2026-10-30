"""The Pi service preparation command is deterministic and never installs secrets."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.prepare_pi_node_service import prepare_service_bundle


class PreparePiNodeServiceTests(unittest.TestCase):
    def test_prepares_hardened_unit_and_placeholder_only_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            unit_path, env_path = prepare_service_bundle(
                output,
                project_root="/srv/aura-node",
                environment_file="/etc/aura/custom-node.env",
            )
            unit = unit_path.read_text(encoding="utf-8")
            config = env_path.read_text(encoding="utf-8")
            self.assertIn("WorkingDirectory=/srv/aura-node", unit)
            self.assertIn("EnvironmentFile=/etc/aura/custom-node.env", unit)
            self.assertIn("NoNewPrivileges=true", unit)
            self.assertIn("MemoryMax=128M", unit)
            self.assertNotIn("AURA_SENSOR_NODE_TOKEN=", unit)
            self.assertIn("AURA_SENSOR_NODE_TOKEN=replace-with-one-time-enrollment-token", config)
            self.assertIn("Copy to /etc/aura/custom-node.env", config)
            if os.name != "nt":
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertEqual(unit_path.stat().st_mode & 0o777, 0o644)
                self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_refuses_path_injection_and_never_overwrites_existing_templates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "bundle"
            output.mkdir(mode=0o700)
            for project_root in ("relative/path", "/opt/aura;touch /tmp/pwned", "/opt/../etc/aura"):
                with self.subTest(project_root=project_root), self.assertRaises(ValueError):
                    prepare_service_bundle(output, project_root=project_root)
            unit_path, env_path = prepare_service_bundle(output)
            unit_before = unit_path.read_text(encoding="utf-8")
            env_path.write_text("owner data", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_service_bundle(output)
            self.assertEqual(unit_path.read_text(encoding="utf-8"), unit_before)
            self.assertEqual(env_path.read_text(encoding="utf-8"), "owner data")

    @unittest.skipIf(os.name == "nt", "Windows symlink creation requires elevated privileges")
    def test_refuses_symlinked_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = root / "actual"
            actual.mkdir()
            link = root / "linked"
            link.symlink_to(actual, target_is_directory=True)
            with self.assertRaises(ValueError):
                prepare_service_bundle(link)


if __name__ == "__main__":
    unittest.main()
