"""Kaggle active competitions (Kaggle API, HTTP basic auth with username + key).

Participation rules live in each competition's rules page (age, country), so
eligibility stays unknown until the detail page is checked.
"""

from __future__ import annotations

import base64
import json

from ..contest_model import compact_date, empty_details, make_contest, schedule_item, short, today_kst
from . import http


SOURCE = {
    "id": "kaggle",
    "name": "Kaggle 데이터 경진대회",
    "type": "official_api",
    "env": ["KAGGLE_USERNAME", "KAGGLE_KEY"],
    "homepage": "https://www.kaggle.com/docs/api",
    "description": "Kaggle 공식 API · 진행 중인 해외 데이터·AI 경진대회",
}
BASE = "https://www.kaggle.com/api/v1/competitions/list"


def _value(item: dict, *names):
    for name in names:
        if item.get(name) not in (None, ""):
            return item[name]
    return None


def normalize(item: dict, collected_at: str | None = None) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = str(_value(item, "title", "competitionTitle") or "").strip()
    ref = str(_value(item, "ref", "competitionRef", "url") or "").strip()
    if len(title) < 3 or not ref:
        return None
    url = ref if ref.startswith("https://") else f"https://www.kaggle.com/competitions/{ref.rsplit('/', 1)[-1]}"
    deadline = compact_date(_value(item, "deadline", "deadlineDate"))
    if deadline and deadline < today_kst().isoformat():
        return None
    details = empty_details()
    details["schedule"] = [entry for entry in (
        schedule_item("apply", "참가 가능 기간", compact_date(_value(item, "enabledDate", "dateEnabled")),
                      compact_date(_value(item, "newEntrantDeadline")) or deadline, "Kaggle API 일정"),
        schedule_item("event", "최종 제출 마감", None, deadline, "Kaggle API deadline"),
    ) if entry]
    reward = _value(item, "reward", "rewardDisplay")
    if reward:
        details["reward"] = {"value": short(reward, 80), "evidence": "Kaggle API reward"}
    details["deliverables"] = [{"text": "예측 결과 파일 또는 노트북 제출 (대회 규정 확인)", "evidence": "Kaggle competition submission"}]
    if item.get("maxTeamSize"):
        details["team_note"] = f"최대 팀 인원 {item['maxTeamSize']}명"
    details["summary"] = short(_value(item, "description", "subtitle"), 300)
    details["links"] = [{"label": "Kaggle 대회 페이지", "url": url}, {"label": "대회 규정", "url": url.rstrip("/") + "/rules"}]
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"], key=url, title=title,
        source_url=url, kind="competition", organizer=_value(item, "organizationName") or "Kaggle", deadline=deadline,
        category="데이터·AI", eligibility_known=False, details=details, collected_at=collected_at,
    )


def parse(payload) -> list[dict]:
    rows = payload if isinstance(payload, list) else payload.get("competitions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise http.SourceError("Kaggle 응답 형식이 예상과 다릅니다")
    return [contest for contest in (normalize(row) for row in rows) if contest]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        return parse(json.loads(http.fixture("kaggle.json")))
    token = base64.b64encode(f"{env.get('KAGGLE_USERNAME', '')}:{env.get('KAGGLE_KEY', '')}".encode()).decode()
    payload = http.get_json(BASE, {"sortBy": "latestDeadline", "page": 1},
                            {"Authorization": f"Basic {token}"}, source="Kaggle API")
    return parse(payload)
