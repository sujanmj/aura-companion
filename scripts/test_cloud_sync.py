"""Offline tests for optional, server-side Supabase record sync."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cloud.supabase_sync import sync_conversation, sync_sensor_event


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class CloudSyncTests(unittest.TestCase):
    def test_missing_settings_leave_local_app_offline(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch(
            "cloud.supabase_sync.urllib.request.urlopen"
        ) as open_url:
            self.assertFalse(sync_conversation(1, "user", "hello", "2026-01-01T00:00:00Z"))
            self.assertFalse(sync_sensor_event({"event_id": 1, "event_type": "fire"}))
            open_url.assert_not_called()

    def test_conversation_sync_keeps_key_in_server_request(self) -> None:
        settings = {
            "AURA_SUPABASE_URL": "https://example.supabase.co",
            "AURA_SUPABASE_SERVICE_ROLE_KEY": "server-secret",
            "AURA_CLOUD_DEVICE_ID": "aura-pi-main",
        }
        with patch.dict(os.environ, settings, clear=True), patch(
            "cloud.supabase_sync.urllib.request.urlopen", return_value=FakeResponse()
        ) as open_url:
            self.assertTrue(sync_conversation(14, "assistant", "Hello", "2026-01-01T00:00:00Z"))
        request = open_url.call_args.args[0]
        self.assertIn("aura_conversations?on_conflict=device_id,local_id", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer server-secret")
        self.assertEqual(json.loads(request.data)["device_id"], "aura-pi-main")

    def test_rejects_non_https_cloud_endpoint(self) -> None:
        settings = {
            "AURA_SUPABASE_URL": "http://example.supabase.co",
            "AURA_SUPABASE_SERVICE_ROLE_KEY": "server-secret",
            "AURA_CLOUD_DEVICE_ID": "aura-pi-main",
        }
        with patch.dict(os.environ, settings, clear=True), patch(
            "cloud.supabase_sync.urllib.request.urlopen"
        ) as open_url:
            self.assertFalse(sync_sensor_event({"event_id": 1, "event_type": "fire", "event_summary": "test"}))
            open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
