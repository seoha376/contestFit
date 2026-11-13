"""한국콘텐츠진흥원 지원사업 공고 (kocca.kr OPEN API, key from KOCCA).

The list response includes the posting body, so eligibility and schedule come
from the same official text through the shared extractor.
"""

from __future__ import annotations

import json

from ..contest_model import compact_date, kind_from_title, make_contest, schedule_item, short, today_kst
from ..details import merge_details
from ..page_extract import analyze_text
from ..parser import html_to_text
from . import http


SOURCE = {
    "id": "kocca",
    "name": "한국콘텐츠진흥원 지원사업",
    "type": "official_api",
    "env": ["KOCCA_SERVICE_KEY"],
    "homepage": "https://www.kocca.kr/kocca/subPage.do?menuNo=204796&gubun=tab01",
    "description": "콘텐츠진흥원 공식 API · 자유공모·지정공모·모집공고",
}
BASE = "https://kocca.kr/api/pims/List.do"
CATEGORIES = {"1": "자유공모", "2": "지정공모", "3": "모집공고"}


def normalize(item: dict, collected_at: str | None = None) -> dict | None:
    title = str(item.get("title") or "").strip()
    if len(title) < 3:
        return None
    end = compact_date(item.get("endDt"))
    if end and end < today_kst().isoformat():
        return None
    start = compact_date(item.get("startDt"))
    link = str(item.get("link") or "").strip()
    url = link if link.startswith("http") else "https://" + link.lstrip("/") if link else "https://www.kocca.kr/kocca/pims/list.do?menuNo=204104"
    body = html_to_text(str(item.get("content") or "")) if "<" in str(item.get("content") or "") else str(item.get("content") or "")
    analysis = analyze_text(url, f"{title}\n{body}")
    details = merge_details({"schedule": [entry for entry in [schedule_item("apply", "접수", start, end, f"접수 {item.get('startDt')}~{item.get('endDt')}")] if entry],
                             "links": [{"label": "콘텐츠진흥원 공고", "url": url}]}, analysis["details"])
    details["summary"] = short(body, 400)
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"],
        key=str(item.get("intcNoSeq") or url), title=title, source_url=url,
        kind=kind_from_title(title, "support"), organizer="한국콘텐츠진흥원", deadline=end,
        category=item.get("cate") or item.get("cata"), sections=analysis["sections"],
        eligibility_known=analysis["eligibility_found"], details=details, collected_at=collected_at,
    )


def parse(payload) -> list[dict]:
    info = payload.get("INFO") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        raise http.SourceError("콘텐츠진흥원 응답 형식이 예상과 다릅니다")
    code = info.get("resultCode")
    if code == "INFO-200":
        return []
    if code != "INFO-000":
        raise http.SourceError(f"콘텐츠진흥원 API 오류 {code}")
    rows = info.get("list") or []
    return [contest for contest in (normalize(row) for row in rows if isinstance(row, dict)) if contest]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        return parse(json.loads(http.fixture("kocca.json")))
    found: dict[str, dict] = {}
    for cate in CATEGORIES:
        payload = http.get_json(BASE, {
            "serviceKey": env.get("KOCCA_SERVICE_KEY", ""), "cate": cate, "pageNo": 1, "numOfRows": 50,
        }, source="콘텐츠진흥원 API")
        for contest in parse(payload):
            found[contest["id"]] = contest
    return list(found.values())
