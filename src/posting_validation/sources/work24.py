"""고용24 채용정보 OPEN API (인턴 공고, authKey from work24.go.kr).

Only postings whose title says 인턴 are kept. Education and career requirements
are listed as conditions to check because the profile does not record them.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..contest_model import compact_date, empty_details, empty_section, make_contest, schedule_item, set_condition, today_kst
from . import http


SOURCE = {
    "id": "work24",
    "name": "고용24 인턴 채용",
    "type": "official_api",
    "env": ["WORK24_AUTH_KEY"],
    "homepage": "https://www.work24.go.kr/cm/e/a/0110/selectOpenApiSvcInfo.do",
    "description": "고용노동부 고용24 공식 API · 인턴 채용 공고",
}
BASE = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"
OPEN_EDUCATION = re.compile(r"학력\s*무관|무관|관계\s*없음")
OPEN_CAREER = re.compile(r"신입|관계\s*없음|무관")


def _text(node, name: str) -> str:
    child = node.find(name)
    return (child.text or "").strip() if child is not None and child.text else ""


def normalize(node, collected_at: str | None = None) -> dict | None:
    title = _text(node, "title")
    if not re.search(r"인턴", title):
        return None
    close = _text(node, "closeDt")
    deadline = compact_date(close)
    if deadline and deadline < today_kst().isoformat():
        return None
    url = _text(node, "wantedInfoUrl") or _text(node, "wantedMobileInfoUrl")
    if not url.startswith("http"):
        return None
    section = empty_section("tmp")
    education = _text(node, "minEdubg")
    career = _text(node, "career")
    conditions, evidence = [], []
    if education and not OPEN_EDUCATION.search(education):
        conditions.append(f"학력: {education} 이상")
        evidence.append(f"최소학력 {education}")
    if career and not OPEN_CAREER.search(career):
        conditions.append(f"경력: {career}")
        evidence.append(f"경력 {career}")
    if conditions:
        set_condition(section, "other_conditions", conditions, evidence)
    details = empty_details()
    details["schedule"] = [entry for entry in [schedule_item("apply", "접수", compact_date(_text(node, "regDt")), deadline,
                                                             f"등록 {_text(node, 'regDt')} · 마감 {close}")] if entry]
    pay = " ".join(value for value in (_text(node, "salTpNm"), _text(node, "sal")) if value)
    details["job"] = {
        "company": _text(node, "company"), "region": _text(node, "region"), "pay": pay or None,
        "education": education or None, "career": career or None, "schedule": _text(node, "holidayTpNm") or None,
    }
    details["apply_method"] = {"value": "고용24 채용 공고 페이지에서 지원", "evidence": "고용24 채용정보 API"}
    details["deliverables"] = [{"text": "이력서·자기소개서 (공고별 양식 확인)", "evidence": "고용24 입사지원"}]
    details["links"] = [{"label": "고용24 공고", "url": url}]
    if not deadline and "채용시" in close:
        details["deadline_note"] = "채용 시까지"
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"],
        key=_text(node, "wantedAuthNo") or url, title=title, source_url=url, kind="internship",
        organizer=_text(node, "company"), deadline=deadline, category="인턴·채용",
        sections=[section], eligibility_known=True, details=details, collected_at=collected_at,
    )


def parse(data: bytes) -> list[dict]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise http.SourceError("고용24 응답이 XML 형식이 아닙니다") from None
    if root.tag != "wantedRoot":
        message = root.findtext(".//message") or root.findtext(".//messageCd") or root.tag
        raise http.SourceError(f"고용24 API 오류: {message[:60]}")
    return [contest for contest in (normalize(node) for node in root.findall("wanted")) if contest]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        return parse(http.fixture("work24.xml"))
    data = http.get(BASE, {
        "authKey": env.get("WORK24_AUTH_KEY", ""), "callTp": "L", "returnType": "XML",
        "startPage": 1, "display": 100, "keyword": "인턴",
    }, source="고용24 API")
    return parse(data)
