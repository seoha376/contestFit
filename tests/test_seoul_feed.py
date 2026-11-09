from __future__ import annotations

import unittest
from datetime import date

from posting_validation.seoul_feed import parse_listing


class SeoulFeedTests(unittest.TestCase):
    def test_only_open_dated_official_listing_links_become_candidates(self) -> None:
        markup = """
        <a href="/gongmo/123"><p class="tit ellipsis_66">서울 AI &amp; 데이터 공모전</p>
        <p class="date">2026.10.01. ~ 2026.11.20.</p><p class="type"><span>AI, 데이터</span></p></a>
        <a href="/gongmo/123"><p class="tit">서울 AI &amp; 데이터 공모전</p>
        <p class="date">2026.10.01. ~ 2026.11.20.</p></a>
        <a href="/gongmo/456"><p class="tit">지난 공모전</p>
        <p class="date">2026.09.01. ~ 2026.10.31.</p></a>
        <a href="https://example.com/contest"><p class="tit">외부 사이트</p>
        <p class="date">2026.10.01. ~ 2026.11.20.</p></a>
        """
        result = parse_listing(markup, date(2026, 11, 9))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_url"], "https://mediahub.seoul.go.kr/gongmo/123")
        self.assertEqual(result[0]["title"], "서울 AI & 데이터 공모전")
        self.assertEqual(result[0]["deadline"], "2026-11-20")
        self.assertEqual(result[0]["organizer"], "")


if __name__ == "__main__":
    unittest.main()
