from __future__ import annotations

import ssl
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.sensor_api_server import server_tls_context
from config.sensor_transport import is_safe_sensor_api_url


class SensorTransportTests(unittest.TestCase):
    def test_http_is_restricted_to_loopback_and_https_is_allowed(self) -> None:
        for url in (
            "http://127.0.0.1:8787",
            "http://localhost:8787",
            "http://[::1]:8787",
            "https://aura-hub.example.test:8787",
        ):
            with self.subTest(url=url):
                self.assertTrue(is_safe_sensor_api_url(url))
        for url in (
            "http://192.168.1.20:8787",
            "http://aura-hub.local:8787",
            "ftp://aura-hub.example.test",
            "https://aura-hub.example.test:bad",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_safe_sensor_api_url(url))

    def test_loopback_server_keeps_local_development_http(self) -> None:
        self.assertIsNone(server_tls_context("127.0.0.1", {}))
        self.assertIsNone(server_tls_context("localhost", {}))

    def test_network_bind_without_tls_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "TLS certificate and private key"):
            server_tls_context("0.0.0.0", {})
        with self.assertRaisesRegex(ValueError, "TLS certificate and private key"):
            server_tls_context("aura-hub.local", {})

    def test_network_bind_uses_tls_12_or_newer_and_configured_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cert = root / "server.crt"
            key = root / "server.key"
            cert.write_text("placeholder")
            key.write_text("placeholder")
            key.chmod(0o640)
            with patch.object(ssl.SSLContext, "load_cert_chain") as load_cert_chain:
                context = server_tls_context("0.0.0.0", {
                    "AURA_SENSOR_TLS_CERT_FILE": str(cert),
                    "AURA_SENSOR_TLS_KEY_FILE": str(key),
                })
            self.assertIsInstance(context, ssl.SSLContext)
            self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
            load_cert_chain.assert_called_once_with(certfile=str(cert), keyfile=str(key))

    def test_network_bind_rejects_missing_or_insecure_key_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cert = root / "server.crt"
            key = root / "server.key"
            cert.write_text("placeholder")
            key.write_text("placeholder")
            key.chmod(0o640)
            env = {
                "AURA_SENSOR_TLS_CERT_FILE": str(cert),
                "AURA_SENSOR_TLS_KEY_FILE": str(key),
            }
            key.unlink()
            with self.assertRaisesRegex(ValueError, "regular files"):
                server_tls_context("0.0.0.0", env)
            key.write_text("placeholder")
            key.chmod(0o644)
            if sys.platform != "win32":
                with self.assertRaisesRegex(ValueError, "permissions"):
                    server_tls_context("0.0.0.0", env)

    @unittest.skipUnless(os.name == "posix", "symlink creation is not portable on Windows")
    def test_network_bind_rejects_symlinked_certificate_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            cert_target = root / "real.crt"
            cert_link = root / "server.crt"
            key = root / "server.key"
            cert_target.write_text("placeholder")
            cert_link.symlink_to(cert_target)
            key.write_text("placeholder")
            key.chmod(0o640)
            with self.assertRaisesRegex(ValueError, "regular files"):
                server_tls_context("0.0.0.0", {
                    "AURA_SENSOR_TLS_CERT_FILE": str(cert_link),
                    "AURA_SENSOR_TLS_KEY_FILE": str(key),
                })

    @unittest.skipUnless(os.name == "posix", "symlink creation is not portable on Windows")
    def test_network_bind_rejects_symlinked_certificate_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            actual = root / "actual"
            actual.mkdir()
            (actual / "server.crt").write_text("placeholder")
            key = root / "server.key"
            key.write_text("placeholder")
            key.chmod(0o640)
            (root / "alias").symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "regular files"):
                server_tls_context("0.0.0.0", {
                    "AURA_SENSOR_TLS_CERT_FILE": str(root / "alias" / "server.crt"),
                    "AURA_SENSOR_TLS_KEY_FILE": str(key),
                })


if __name__ == "__main__":
    unittest.main()
