"""커리어넷 학과정보 OPEN API (major families for matching 전공 conditions)."""

from __future__ import annotations

import json

from . import http


SOURCE = {
    "id": "careernet",
    "name": "커리어넷 학과정보",
    "type": "reference_api",
    "env": ["CAREERNET_API_KEY"],
    "homepage": "https://www.career.go.kr/cnet/front/openapi/openApiMajorCenter.do",
    "description": "교육부 커리어넷 공식 API · 학과 계열·관련 학과",
}
BASE = "https://www.career.go.kr/cnet/openapi/getOpenApi"
# 커리어넷 계열을 학과 카탈로그(전국대학별학과정보) 계열 값으로 맞춘다.
FAMILY_ALIASES = {"공학계열": "공학", "자연계열": "자연과학", "인문계열": "인문사회", "사회계열": "인문사회",
                  "교육계열": "교육", "의약계열": "의학", "예체능계열": "예체능"}


def parse(payload) -> list[dict]:
    search = payload.get("dataSearch") if isinstance(payload, dict) else None
    content = search.get("content") if isinstance(search, dict) else None
    if content is None:
        raise http.SourceError("커리어넷 응답 형식이 예상과 다릅니다")
    rows = content if isinstance(content, list) else [content]
    majors = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("mClass"):
            continue
        family = str(row.get("lClass") or "").strip()
        majors.append({
            "major": str(row.get("mClass")).strip(),
            "family": FAMILY_ALIASES.get(family, family.replace("계열", "")) or None,
            "related": [name.strip() for name in str(row.get("facilName") or "").split(",") if name.strip()][:12],
            "major_seq": str(row.get("majorSeq") or ""),
        })
    return majors


def search(env: dict, query: str) -> list[dict]:
    query = query.strip()[:40]
    if len(query) < 2:
        return []
    if http.mode() == "fixture":
        rows = parse(json.loads(http.fixture("careernet.json")))
        return [row for row in rows if query in row["major"] or any(query in name for name in row["related"])]
    payload = http.get_json(BASE, {
        "apiKey": env.get("CAREERNET_API_KEY", ""), "svcType": "api", "svcCode": "MAJOR", "contentType": "json",
        "gubun": "univ_list", "searchTitle": query, "perPage": 20,
    }, source="커리어넷 API")
    return parse(payload)
