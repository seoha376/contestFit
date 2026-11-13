"""Codeforces upcoming rounds (public API, no key).

Anyone with a Codeforces account can enter Div. 2/3/4 and Educational rounds;
rating only decides whether the round is rated. Div. 1-only rounds restrict
registration, so they are left as a condition to check.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from ..contest_model import KST, empty_details, empty_section, make_contest, schedule_item, set_condition
from . import http


SOURCE = {
    "id": "codeforces",
    "name": "Codeforces 프로그래밍 대회",
    "type": "official_api",
    "env": [],
    "homepage": "https://codeforces.com/apiHelp",
    "description": "Codeforces 공식 API · 예정된 해외 알고리즘 대회 (키 불필요)",
}
BASE = "https://codeforces.com/api/contest.list"


def normalize(item: dict, collected_at: str | None = None) -> dict | None:
    if not isinstance(item, dict) or item.get("phase") != "BEFORE" or not item.get("startTimeSeconds"):
        return None
    title = str(item.get("name") or "").strip()
    start = datetime.fromtimestamp(int(item["startTimeSeconds"]), UTC).astimezone(KST)
    date_text = start.date().isoformat()
    url = f"https://codeforces.com/contests/{item.get('id')}"
    section = empty_section("tmp")
    evidence = f"{title} — Codeforces 계정으로 등록"
    if re.search(r"Div\.\s*1(?!\s*\+)", title) and not re.search(r"Div\.\s*2", title):
        set_condition(section, "other_conditions", ["Div. 1 단독 라운드: 레이팅 1900 이상 등록"], evidence)
    details = empty_details()
    hours = int(item.get("durationSeconds") or 0) // 3600
    minutes = (int(item.get("durationSeconds") or 0) % 3600) // 60
    details["schedule"] = [schedule_item("event", "대회 시작", date_text, None,
                                         f"시작 {start.strftime('%Y-%m-%d %H:%M')} KST · {hours}시간 {minutes}분")]
    details["apply_method"] = {"value": "Codeforces 대회 페이지에서 Register (시작 전까지)", "evidence": "Codeforces contest registration"}
    details["deliverables"] = [{"text": "대회 중 문제 풀이 코드 제출", "evidence": "Codeforces 온라인 채점"}]
    details["links"] = [{"label": "Codeforces 대회 목록", "url": url}]
    details["start_time"] = start.isoformat()
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"], key=str(item.get("id")),
        title=title, source_url=url, kind="competition", organizer="Codeforces", deadline=date_text,
        category="프로그래밍·알고리즘", sections=[section], eligibility_known=True, details=details,
        collected_at=collected_at,
    )


def parse(payload) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("status") != "OK" or not isinstance(payload.get("result"), list):
        raise http.SourceError("Codeforces 응답 형식이 예상과 다릅니다")
    contests = [contest for contest in (normalize(item) for item in payload["result"]) if contest]
    return sorted(contests, key=lambda item: item["deadline"])[:15]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        return parse(json.loads(http.fixture("codeforces.json")))
    return parse(http.get_json(BASE, {"gym": "false"}, source="Codeforces API"))
