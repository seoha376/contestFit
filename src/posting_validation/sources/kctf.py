"""K-CTF 정보보안 대회 (k-ctf.org API, Bearer key)."""

from __future__ import annotations

import json

from ..contest_model import compact_date, empty_details, make_contest, schedule_item, today_kst
from . import http


SOURCE = {
    "id": "kctf",
    "name": "K-CTF 정보보안 대회",
    "type": "official_api",
    "env": ["KCTF_API_KEY"],
    "homepage": "https://k-ctf.org/api/docs",
    "description": "K-CTF 공식 API · 접수 중인 CTF·보안 대회",
}
BASE = "https://k-ctf.org/api/v1/contests"


def normalize(item: dict, collected_at: str | None = None) -> dict | None:
    if not isinstance(item, dict) or item.get("registration_status") == "registration_closed":
        return None
    title = str(item.get("name") or "").strip()
    if len(title) < 3:
        return None
    deadline = compact_date(item.get("apply_end_date"))
    if deadline and deadline < today_kst().isoformat():
        return None
    url = next((str(value).strip() for value in (item.get("link"), item.get("url")) if str(value or "").startswith("https://")), None)
    if not url:
        return None
    details = empty_details()
    details["schedule"] = [entry for entry in (
        schedule_item("apply", "접수", compact_date(item.get("apply_start_date")), deadline, "K-CTF API 접수 기간"),
        schedule_item("event", "대회", compact_date(item.get("start_date")), compact_date(item.get("end_date")), "K-CTF API 대회 일정"),
    ) if entry]
    details["links"] = [{"label": "대회 공식 페이지", "url": url}]
    if item.get("format") or item.get("type"):
        details["summary"] = f"형식: {item.get('format') or item.get('type')}"
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"],
        key=str(item.get("id") or url), title=title, source_url=url, kind="competition",
        organizer=item.get("host") or item.get("organizer"), deadline=deadline, category="정보보안·CTF",
        eligibility_known=False, details=details, collected_at=collected_at,
    )


def parse(payload) -> list[dict]:
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise http.SourceError("K-CTF 응답 형식이 예상과 다릅니다")
    return [contest for contest in (normalize(item) for item in items) if contest]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        return parse(json.loads(http.fixture("kctf.json")))
    found: dict[str, dict] = {}
    for page in (1, 2):
        payload = http.get_json(BASE, {"status": "registering", "page": page, "page_size": 50},
                                {"Authorization": f"Bearer {env.get('KCTF_API_KEY', '')}"}, source="K-CTF API")
        for contest in parse(payload):
            found[contest["id"]] = contest
        if not isinstance(payload.get("total"), int) or page * 50 >= payload["total"]:
            break
    return list(found.values())
