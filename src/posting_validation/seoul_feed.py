"""Collect metadata-only candidates from Seoul's official contest listing.

This source covers Seoul's own portal, not every contest in Korea. A collected
candidate remains unpublished until the original posting is reviewed.
"""

from __future__ import annotations

import argparse
import html
import re
import time
import urllib.request
import urllib.robotparser
from datetime import date, timedelta

from .candidates import import_candidates


LIST_URL = "https://mediahub.seoul.go.kr/competition/competitionList.do"
ROBOTS_URL = "https://mediahub.seoul.go.kr/robots.txt"
USER_AGENT = "ContestFit/1.0 (official contest metadata, manually triggered)"
ANCHOR = re.compile(r'<a\s+href="(/gongmo/\d+)"[^>]*>(.*?)</a>', re.I | re.S)
DATE = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})")


def _plain(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


def _field(fragment: str, name: str) -> str:
    match = re.search(rf'<p\s+class="[^"]*\b{name}\b[^"]*"[^>]*>(.*?)</p>', fragment, re.I | re.S)
    return _plain(match.group(1)) if match else ""


def parse_listing(markup: str, today: date | None = None) -> list[dict]:
    today = today or date.today()
    found: dict[str, dict] = {}
    for match in ANCHOR.finditer(markup):
        title = _field(match.group(2), "tit")
        dates = DATE.findall(_field(match.group(2), "date"))
        if len(title) < 3 or len(dates) < 2:
            continue
        year, month, day = map(int, dates[-1])
        try:
            deadline = date(year, month, day)
        except ValueError:
            continue
        if not today <= deadline <= today + timedelta(days=180):
            continue
        url = "https://mediahub.seoul.go.kr" + match.group(1)
        found[url] = {
            "source_url": url,
            "title": title,
            "organizer": "",
            "deadline": deadline.isoformat(),
            "category": _field(match.group(2), "type"),
            "source_name": "서울시 공식 공모전 목록",
        }
    return sorted(found.values(), key=lambda item: (item["deadline"], item["title"]))[:20]


def fetch_listing() -> str:
    with urllib.request.urlopen(urllib.request.Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT}), timeout=15) as response:
        robots_text = response.read(100_000).decode("utf-8", errors="replace")
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(robots_text.splitlines())
    if not robots.can_fetch(USER_AGENT, LIST_URL):
        raise RuntimeError("서울시 공식 목록의 robots.txt가 수집을 허용하지 않습니다.")
    time.sleep(max(3.0, robots.crawl_delay(USER_AGENT) or 0))
    with urllib.request.urlopen(urllib.request.Request(LIST_URL, headers={"User-Agent": USER_AGENT}), timeout=15) as response:
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise RuntimeError("서울시 공식 목록이 HTML을 반환하지 않았습니다.")
        page = response.read(1_000_001)
        if len(page) > 1_000_000:
            raise RuntimeError("서울시 공식 목록이 예상보다 커서 수집을 중단했습니다.")
        return page.decode("utf-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect open metadata-only candidates from Seoul's official list")
    parser.add_argument("--dry-run", action="store_true", help="report candidate count without changing files")
    args = parser.parse_args()
    candidates = parse_listing(fetch_listing())
    if not candidates:
        raise RuntimeError("접수 중인 공고를 파싱하지 못했습니다. 기존 후보 파일을 유지합니다.")
    if args.dry_run:
        print(f"서울시 공식 목록에서 접수 중인 후보 {len(candidates)}건을 확인했습니다. 저장하지 않았습니다.")
    else:
        result = import_candidates(candidates)
        print(f"서울시 후보 {result['imported']}건 반영, 전체 후보 {result['total']}건")


if __name__ == "__main__":
    main()
