import io
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api.sensor_api_server import AuraSensorAPIHandler


class ResponseHarness:
    def __init__(self) -> None:
        self.status = None
        self.headers = []
        self.wfile = io.BytesIO()

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, name: str, value: str) -> None:
        self.headers.append((name, value))

    def end_headers(self) -> None:
        pass

    def _send_json(self, status: int, payload: dict) -> None:
        AuraSensorAPIHandler._send_json(self, status, payload)


class SensorAPIResponseHeaderTests(unittest.TestCase):
    def test_json_responses_are_not_stored_by_http_caches(self) -> None:
        response = ResponseHarness()

        AuraSensorAPIHandler._send_json(response, 200, {"ok": True, "nodes": []})

        self.assertEqual(response.status, 200)
        self.assertIn(("Cache-Control", "no-store"), response.headers)
        self.assertIn(("Content-Type", "application/json; charset=utf-8"), response.headers)
        self.assertEqual(int(dict(response.headers)["Content-Length"]), len(response.wfile.getvalue()))
        self.assertEqual(json.loads(response.wfile.getvalue()), {"ok": True, "nodes": []})

    def test_unauthorized_json_responses_are_also_not_cacheable(self) -> None:
        response = ResponseHarness()

        AuraSensorAPIHandler._send_unauthorized(response)

        self.assertEqual(response.status, 401)
        self.assertIn(("Cache-Control", "no-store"), response.headers)
        self.assertEqual(json.loads(response.wfile.getvalue()), {"ok": False, "error": "unauthorized"})


if __name__ == "__main__":
    unittest.main()
