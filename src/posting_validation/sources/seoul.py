"""서울시 공식 공모전 목록 (mediahub.seoul.go.kr, robots-checked, no key)."""

from __future__ import annotations

from ..contest_model import empty_details, make_contest, schedule_item
from ..seoul_feed import fetch_listing, parse_listing
from . import http


SOURCE = {
    "id": "seoul",
    "name": "서울시 공모전",
    "type": "official_list",
    "env": [],
    "homepage": "https://mediahub.seoul.go.kr/competition/competitionList.do",
    "description": "서울시 공식 공모전 목록 · 접수 중인 공고 (키 불필요)",
}


def normalize(candidate: dict, collected_at: str | None = None) -> dict:
    details = empty_details()
    details["schedule"] = [entry for entry in [schedule_item("apply", "접수 마감", None, candidate["deadline"], "서울시 공모전 목록")] if entry]
    details["links"] = [{"label": "서울시 공모 상세", "url": candidate["source_url"]}]
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"], key=candidate["source_url"],
        title=candidate["title"], source_url=candidate["source_url"], kind="contest", organizer="서울특별시 및 유관기관",
        deadline=candidate["deadline"], category=candidate.get("category") or None, eligibility_known=False,
        details=details, collected_at=collected_at,
    )


def parse(markup: str) -> list[dict]:
    return [normalize(candidate) for candidate in parse_listing(markup)]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        return parse(http.fixture("seoul.html").decode("utf-8"))
    try:
        return parse(fetch_listing())
    except RuntimeError as exc:
        raise http.SourceError(str(exc)[:80]) from None
    except OSError:
        raise http.SourceError("서울시 목록 연결 실패") from None
