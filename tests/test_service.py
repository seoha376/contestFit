from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch

from posting_validation import service, store
from posting_validation.curate import publish, verify_contest


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        # Unit tests never call live APIs or touch the developer's tmp/ store.
        self._directory = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {"CONTESTFIT_SOURCE_MODE": "off"})
        self._env.start()
        store.reset_store(store.LocalStore(Path(self._directory.name)))

    def tearDown(self) -> None:
        store.reset_store(None)
        self._env.stop()
        self._directory.cleanup()

    def test_http_data_contract_uses_saved_catalog_and_excludes_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.json"
            curated = root / "curated.json"
            catalog = root / "departments.json"
            seed.write_text(json.dumps({"schema_version": "1.1", "contests": [
                {"id": "sample-1", "title": "샘플", "is_sample": True, "validation_status": "unverified"},
            ]}, ensure_ascii=False), encoding="utf-8")
            curated.write_text(json.dumps({"contests": [
                {"id": "real-1", "title": "검수 공고", "is_sample": False, "validation_status": "verified"},
            ]}, ensure_ascii=False), encoding="utf-8")
            catalog.write_text(json.dumps({"reference_year": 2025, "synced_at": "2026-11-09T00:00:00+00:00",
                "school_count": 1, "schools": [{"name": "서울예시대학교", "region": "서울"}],
                "departments": [{"school": "서울예시대학교", "major": "컴퓨터공학과", "region": "서울"}]
            }, ensure_ascii=False), encoding="utf-8")

            class QuietHandler(service.Handler):
                def log_message(self, *args) -> None:
                    pass

            with patch.object(service, "SEED", seed), patch.object(service, "CURATED", curated), patch.object(service, "CATALOG", catalog):
                with ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        base = f"http://127.0.0.1:{server.server_port}"

                        def get(path):
                            with urlopen(base + path, timeout=2) as response:
                                self.assertEqual(response.status, 200)
                                return json.load(response)

                        contests = get("/api/contests")
                        self.assertEqual([item["id"] for item in contests["contests"]], ["real-1", "sample-1"])
                        self.assertEqual([item["id"] for item in get("/api/contests?kind=real")["contests"]], ["real-1"])
                        self.assertEqual(get("/api/schools?q=%EC%84%9C%EC%9A%B8")["schools"][0]["name"], "서울예시대학교")
                        self.assertEqual(get("/api/departments?q=%EC%BB%B4%ED%93%A8%ED%84%B0")["departments"][0]["major"], "컴퓨터공학과")
                        status = get("/api/data-status")
                        self.assertEqual((status["verified_contests"], status["sample_contests"], status["departments"]), (1, 1, 1))
                        self.assertNotIn("candidates", contests)
                        self.assertNotIn("candidates", status)
                    finally:
                        server.shutdown()
                        thread.join(timeout=2)

    def test_static_es_modules_are_served_as_javascript(self) -> None:
        # Regression: on Windows .mjs came back as text/plain and the page never booted.
        handler = service.Handler.__new__(service.Handler)
        for name in ("app.mjs", "decision-engine.mjs", "config.mjs"):
            self.assertEqual(handler.guess_type(name), "text/javascript", name)

    def test_official_pasted_text_creates_unverified_preview_without_network(self) -> None:
        text = "IT 서비스 아이디어 공모전\n주최: 예시대학교\n참가자격: 대학 재학생만 참가 가능\n만 19세 이상"
        with patch.object(service, "fetch_official_html", side_effect=AssertionError("unexpected network")):
            contest = service.preview_contest("https://example.edu/contest/1", text)
        self.assertFalse(contest["is_sample"])
        self.assertEqual(contest["validation_status"], "draft")
        self.assertEqual(contest["source_url"], "https://example.edu/contest/1")
        self.assertTrue(contest["sections"])

    def test_rejects_non_official_or_local_url(self) -> None:
        for url in ("http://example.edu/contest", "https://127.0.0.1/contest", "https://linkareer.com/activity/1"):
            with self.subTest(url=url):
                if "127.0.0.1" in url:
                    with patch.object(service.socket, "getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
                        with self.assertRaises(service.PreviewError):
                            service.check_public_host(url)
                else:
                    with self.assertRaises(service.PreviewError):
                        service.validate_url(url)

    def test_feedback_stores_only_anonymous_answers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "feedback.jsonl"
            with patch.object(service, "FEEDBACK", target):
                service.record_feedback({"task_completed": True, "reason_clear": False, "ease": 3, "name": "discard me"})
            row = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(row["ease"], 3)
            self.assertNotIn("name", row)

    def test_verified_contest_requires_short_evidence_and_is_published_once(self) -> None:
        contest = service.preview_contest(
            "https://example.edu/contest/1",
            "IT 서비스 아이디어 공모전\n주최: 예시대학교\n참가자격: 대학 재학생만 참가 가능\n만 19세 이상",
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "curated.json"
            publish(contest, target)
            publish(contest, target)
            stored = json.loads(target.read_text(encoding="utf-8"))["contests"]
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["validation_status"], "verified")
        contest["sections"][0]["evidence"]["age"] = None
        if contest["sections"][0]["age"]["min"] is not None:
            with self.assertRaises(ValueError):
                verify_contest(contest)

    def test_contest_query_preserves_default_and_filters_real_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            seed_path = Path(directory) / "seed.json"
            curated_path = Path(directory) / "curated.json"
            seed_path.write_text(json.dumps({"schema_version": "1.1", "contests": [
                {"title": "샘플 공모전", "organizer": "예시", "is_sample": True, "deadline": None},
            ]}, ensure_ascii=False), encoding="utf-8")
            curated_path.write_text(json.dumps({"contests": [
                {"title": "실제 AI 공모전", "organizer": "공식기관", "is_sample": False, "deadline": "2099-12-31", "validation_status": "verified"},
            ]}, ensure_ascii=False), encoding="utf-8")
            with patch.object(service, "SEED", seed_path), patch.object(service, "CURATED", curated_path):
                self.assertEqual(len(service.list_contests()["contests"]), 2)
                filtered = service.list_contests(kind="real", deadline="open", query="AI", limit=1)
                self.assertEqual([item["title"] for item in filtered["contests"]], ["실제 AI 공모전"])
                self.assertEqual(len(service.list_contests(deadline="unknown")["contests"]), 1)
                with self.assertRaises(ValueError):
                    service.list_contests(limit=0)

    def test_data_status_reports_counts_without_exposing_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            seed_path = Path(directory) / "seed.json"
            curated_path = Path(directory) / "curated.json"
            catalog_path = Path(directory) / "departments.json"
            seed_path.write_text(json.dumps({"contests": [{"is_sample": True}]}), encoding="utf-8")
            curated_path.write_text(json.dumps({"contests": [{"is_sample": False, "validation_status": "verified"}]}), encoding="utf-8")
            catalog_path.write_text(json.dumps({"departments": [{"school": "예시대", "major": "컴퓨터공학과"}], "school_count": 1, "reference_year": 2025}), encoding="utf-8")
            with patch.object(service, "SEED", seed_path), patch.object(service, "CURATED", curated_path), patch.object(service, "CATALOG", catalog_path):
                result = service.data_status()
            self.assertEqual((result["sample_contests"], result["verified_contests"], result["departments"], result["schools"]), (1, 1, 1, 1))
            self.assertNotIn("serviceKey", result)


if __name__ == "__main__":
    unittest.main()
