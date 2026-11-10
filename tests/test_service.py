from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from posting_validation import service
from posting_validation.curate import publish, verify_contest


class ServiceTests(unittest.TestCase):
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
