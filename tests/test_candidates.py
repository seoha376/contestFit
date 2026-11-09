from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from posting_validation.candidates import export_review_queue, import_candidates, load_input, read_candidates, summarize


class CandidateTests(unittest.TestCase):
    def test_import_is_atomic_and_deduplicates_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.json"
            row = {"source_url": "https://example.edu/contest/1", "title": "공식 아이디어 공모전", "deadline": "2026-11-13"}
            self.assertEqual(import_candidates([row], path, "2026-11-09T00:00:00+00:00"), {"imported": 1, "total": 1})
            changed = {**row, "title": "공식 아이디어 공모전 수정"}
            import_candidates([changed], path, "2026-11-10T00:00:00+00:00")
            saved = read_candidates(path)["candidates"]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["discovered_at"], "2026-11-09T00:00:00+00:00")
            self.assertEqual(saved[0]["updated_at"], "2026-11-10T00:00:00+00:00")
            with self.assertRaises(ValueError):
                import_candidates([row, {**row, "deadline": "내일"}], path)
            self.assertEqual(read_candidates(path)["candidates"], saved)

    def test_csv_input_and_open_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "input.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["source_url", "title", "deadline"])
                writer.writeheader()
                writer.writerow({"source_url": "https://example.edu/contest/1", "title": "첫 번째 공모전", "deadline": "2026-11-13"})
                writer.writerow({"source_url": "https://example.edu/contest/2", "title": "두 번째 공모전", "deadline": "2026-11-01"})
            rows = load_input(csv_path)
            path = Path(directory) / "candidates.json"
            import_candidates(rows, path, "2026-11-09T00:00:00+00:00")
            report = summarize(read_candidates(path), date(2026, 11, 9))
            self.assertEqual((report["total"], report["open"], report["expired"]), (2, 1, 1))

    def test_review_handoff_marks_only_verified_urls_as_published(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates_path = root / "candidates.json"
            curated_path = root / "curated.json"
            output = root / "queue.csv"
            rows = [
                {"source_url": "https://example.edu/open", "title": "열린 공모전", "deadline": "2026-11-13"},
                {"source_url": "https://example.edu/expired", "title": "지난 공모전", "deadline": "2026-11-01"},
            ]
            import_candidates(rows, candidates_path, "2026-11-09T00:00:00+00:00")
            curated_path.write_text(json.dumps({"contests": [
                {"source_url": "https://example.edu/expired", "validation_status": "verified"},
                {"source_url": "https://example.edu/open", "validation_status": "draft"},
            ]}), encoding="utf-8")
            self.assertEqual(export_review_queue(output, read_candidates(candidates_path), curated_path, date(2026, 11, 9)), 2)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual([(item["deadline_state"], item["review_status"]) for item in exported],
                             [("open", "pending"), ("expired", "published")])
            self.assertNotIn("discovered_at", exported[0])


if __name__ == "__main__":
    unittest.main()
