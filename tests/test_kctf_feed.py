from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from posting_validation.kctf_feed import fetch_candidates, normalize_api_item


class KctfFeedTests(unittest.TestCase):
    def test_api_item_uses_registration_deadline_not_contest_end(self) -> None:
        item = {
            "name": "2026 보안 CTF 대회", "host": "예시 주최기관",
            "registration_status": "registration_open",
            "apply_end_date": "2026-11-20T14:59:00Z",
            "end_date": "2026-11-25T14:59:00Z",
            "link": "https://example.org/contest", "url": "https://k-ctf.org/contests/1",
        }
        candidate = normalize_api_item(item, date(2026, 11, 9))
        self.assertEqual(candidate["deadline"], "2026-11-20")
        self.assertEqual(candidate["source_url"], "https://example.org/contest")
        self.assertEqual(candidate["source_name"], "K-CTF 공식 API")
        self.assertIsNone(normalize_api_item({**item, "registration_status": "registration_closed"}, date(2026, 11, 9)))
        self.assertIsNone(normalize_api_item({**item, "apply_end_date": "2026-11-01T00:00:00Z"}, date(2026, 11, 9)))

    def test_missing_deadline_stays_unknown_and_list_is_paginated(self) -> None:
        item = {
            "name": "정보보안 경진대회", "host": "예시 주최기관",
            "registration_status": "registration_open",
            "url": "https://k-ctf.org/contests/2", "end_date": "2026-11-25T00:00:00Z",
        }
        with patch("posting_validation.kctf_feed._request_json", side_effect=[
            {"total": 51, "items": [item]},
            {"total": 51, "items": [{**item, "url": "https://k-ctf.org/contests/3", "name": "두 번째 CTF 대회"}]},
        ]) as request, patch("posting_validation.kctf_feed.time.sleep"):
            candidates = fetch_candidates("test-key", max_pages=2, today=date(2026, 11, 9))
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["deadline"], "")
        self.assertEqual(request.call_count, 2)
        with self.assertRaisesRegex(ValueError, "KCTF_API_KEY"):
            fetch_candidates("")


if __name__ == "__main__":
    unittest.main()
