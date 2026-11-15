from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from posting_validation import store
from posting_validation.wsgi import app


def call(method: str, path: str, query: str = "", body: bytes = b""):
    captured = {}

    def start_response(status, headers):
        captured["status"] = int(status.split()[0])
        captured["headers"] = dict(headers)

    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
               "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
    data = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], data


class WsgiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"CONTESTFIT_SOURCE_MODE": "fixture"})
        self.env.start()
        store.reset_store(store.LocalStore(Path(self.directory.name)))

    def tearDown(self) -> None:
        store.reset_store(None)
        self.env.stop()
        self.directory.cleanup()

    def test_static_index_and_module_types(self) -> None:
        status, headers, data = call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"CONTEST FIT", data)
        status, headers, _ = call("GET", "/app.mjs")
        self.assertEqual((status, headers["Content-Type"].split(";")[0]), (200, "text/javascript"))
        self.assertEqual(call("GET", "/../pyproject.toml")[0], 404)

    def test_api_lists_fixture_sources_and_accepts_feedback(self) -> None:
        status, _, data = call("GET", "/api/contests", "samples=0")
        payload = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual({item["id"] for item in payload["sources"]},
                         {"kstartup", "kocca", "seoul", "kctf", "codeforces", "kaggle", "work24"})
        self.assertTrue(all(item["status"] == "ok" for item in payload["sources"]))
        self.assertTrue(all(not item["is_sample"] for item in payload["contests"]))
        body = json.dumps({"task_completed": True, "reason_clear": True, "ease": 5}).encode()
        self.assertEqual(call("POST", "/api/feedback", body=body)[0], 201)
        summary = json.loads(call("GET", "/api/feedback-summary")[2])
        self.assertEqual(summary["responses"], 1)

    def test_api_keys_never_appear_in_responses(self) -> None:
        with patch.dict(os.environ, {"DATA_GO_KR_SERVICE_KEY": "SECRET-KEY-123", "KAGGLE_KEY": "SECRET-KAGGLE"}):
            for path in ("/api/contests", "/api/data-status", "/api/sources", "/api/health"):
                data = call("GET", path)[2]
                self.assertNotIn(b"SECRET-KEY-123", data, path)
                self.assertNotIn(b"SECRET-KAGGLE", data, path)


if __name__ == "__main__":
    unittest.main()
