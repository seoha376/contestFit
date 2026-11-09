from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from posting_validation.departments import normalize_departments, response_items, search_catalog, search_schools, sync


class DepartmentTests(unittest.TestCase):
    def test_normalizes_one_year_and_excludes_closed_departments(self) -> None:
        rows = [
            {"YR": "2025", "SCHL_NM": "A대", "SCSBJT_NM": "디자인학과", "CTPV_NM": "서울", "SCSBJT_STTS_NM": "기존"},
            {"YR": "2025", "SCHL_NM": "A대", "SCSBJT_NM": "디자인학과", "CTPV_NM": "서울", "SCSBJT_STTS_NM": "기존"},
            {"YR": "2025", "SCHL_NM": "B대", "SCSBJT_NM": "폐과", "SCSBJT_STTS_NM": "폐지"},
            {"YR": "2024", "SCHL_NM": "C대", "SCSBJT_NM": "컴퓨터공학과"},
        ]
        result = normalize_departments(rows, 2025)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["major"], "디자인학과")

    def test_normalizes_api_camel_case_fields(self) -> None:
        rows = [{
            "yr": "2025", "schlNm": "서울예시대학교", "scsbjtNm": "컴퓨터공학과",
            "ctpvNm": "서울특별시", "scsbjtSttsNm": "기존", "univOneslfAfilNm": "공학계열",
        }]
        self.assertEqual(normalize_departments(rows, 2025), [{
            "school": "서울예시대학교", "major": "컴퓨터공학과", "region": "서울특별시",
            "family": "공학계열", "year": 2025,
        }])

    def test_sync_requires_complete_pages_before_replacing_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "departments.json"
            with patch("posting_validation.departments.fetch_page", side_effect=[([{"YR": "2025", "SCHL_NM": "A대", "SCSBJT_NM": "AI학과"}], 2), ([], 2)]):
                with self.assertRaises(RuntimeError):
                    sync("test-key", 2025, output)
            self.assertFalse(output.exists())

            with patch("posting_validation.departments.fetch_page", return_value=([], 0)):
                with self.assertRaises(RuntimeError):
                    sync("test-key", 2025, output)
            self.assertFalse(output.exists())

    def test_response_and_search_shape(self) -> None:
        rows, total = response_items({"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": {"SCSBJT_NM": "AI학과"}}, "totalCount": 1}}})
        self.assertEqual((len(rows), total), (1, 1))
        rows, total = response_items({"header": {"resultCode": "00"}, "body": {"items": [{"YR": "2025", "SCSBJT_NM": "디자인학과"}], "totalCount": 1}})
        self.assertEqual((rows[0]["SCSBJT_NM"], total), ("디자인학과", 1))
        with self.assertRaisesRegex(ValueError, "body"):
            response_items({"header": {"resultCode": "00"}})
        result = search_catalog({"departments": [{"school": "A대", "major": "AI학과"}]}, "AI")
        self.assertEqual(len(result["departments"]), 1)

    def test_sync_builds_school_index_for_live_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "departments.json"
            rows = [
                {"YR": "2025", "SCHL_NM": "서울예시대학교", "SCSBJT_NM": "AI학과", "CTPV_NM": "서울"},
                {"YR": "2025", "SCHL_NM": "서울예시대학교", "SCSBJT_NM": "디자인학과", "CTPV_NM": "서울"},
            ]
            with patch("posting_validation.departments.fetch_page", return_value=(rows, 2)):
                result = sync("test-key", 2025, output)
            self.assertEqual(result["school_count"], 1)
            self.assertEqual(search_schools(result, "서울")["schools"], [{"name": "서울예시대학교", "region": "서울"}])

    def test_sync_counts_all_api_rows_but_keeps_requested_year(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "departments.json"
            pages = [
                ([{"YR": "2024", "SCHL_NM": "옛대", "SCSBJT_NM": "옛학과"}], 2),
                ([{"YR": "2025", "SCHL_NM": "새대", "SCSBJT_NM": "새학과"}], 2),
            ]
            with patch("posting_validation.departments.fetch_page", side_effect=pages):
                result = sync("test-key", 2025, output)
            self.assertEqual([row["major"] for row in result["departments"]], ["새학과"])

    def test_sync_reports_page_limit_without_replacing_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "departments.json"
            output.write_text("existing", encoding="utf-8")
            with patch("posting_validation.departments.fetch_page", return_value=([{"YR": "2025"}], 3)):
                with self.assertRaisesRegex(RuntimeError, "수신 2건 / 전체 3건"):
                    sync("test-key", 2025, output, max_pages=2)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_school_suggestions_are_unique_and_prefix_first(self) -> None:
        catalog = {"departments": [
            {"school": "과학서울대학교", "major": "컴퓨터공학과", "region": "서울"},
            {"school": "서울과학기술대학교", "major": "컴퓨터공학과", "region": "서울"},
            {"school": "서울과학기술대학교", "major": "디자인학과", "region": "서울"},
        ]}
        result = search_schools(catalog, "서울")
        self.assertEqual(result["count"], 2)
        self.assertEqual([item["name"] for item in result["schools"]], ["서울과학기술대학교", "과학서울대학교"])
        self.assertEqual(search_schools(catalog, "서")["schools"], [])
        indexed = {"school_count": 2, "schools": [
            {"name": "과학서울대학교", "region": "서울"},
            {"name": "서울과학기술대학교", "region": "서울"},
        ]}
        self.assertEqual(search_schools(indexed, "서울")["count"], 2)


if __name__ == "__main__":
    unittest.main()
