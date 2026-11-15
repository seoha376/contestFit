"""창업진흥원 K-Startup 사업공고 (data.go.kr 15125364).

The API returns structured eligibility (신청 대상, 대상 연령, 창업 기간) that maps
directly onto engine conditions. Region and exclusion rules stay as conditions
to check because their basis (residence vs. business site) is not stated.
"""

from __future__ import annotations

import re

from ..contest_model import (
    compact_date, empty_details, empty_section, kind_from_title, make_contest, schedule_item, set_condition, short, today_kst,
)
from ..details import scrub
from . import http


SOURCE = {
    "id": "kstartup",
    "name": "K-Startup 사업공고",
    "type": "official_api",
    "env": ["DATA_GO_KR_SERVICE_KEY"],
    "homepage": "https://www.data.go.kr/data/15125364/openapi.do",
    "description": "창업진흥원 공식 API · 모집 중 창업지원·경진대회 공고",
}
BASE = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
PERSON_TARGETS = {
    "대학생": ["대학생"],
    "대학원생": ["대학원생"],
    "일반인": ["일반인", "직장인", "수료생", "예비창업자", "대학원생"],
    "청소년": ["청소년"],
}
AGE_BANDS = (
    (r"만\s*20\s*세\s*미만", (None, 19)),
    (r"만\s*20\s*세\s*이상\s*~\s*만\s*39\s*세\s*이하", (20, 39)),
    (r"만\s*40\s*세\s*이상", (40, None)),
)


def _age_range(text: str):
    bands = [band for pattern, band in AGE_BANDS if re.search(pattern, text or "")]
    if not bands or len(bands) == len(AGE_BANDS):
        return None
    bands.sort(key=lambda band: -1 if band[0] is None else band[0])
    low, high = bands[0]
    for start, end in bands[1:]:
        if high is None or start is None or start > high + 1:
            return "gap"
        high = end
    return {"min": low, "max": high}


def _business(text: str):
    values = [value.strip() for value in re.split(r"[,，]", text or "") if value.strip()]
    if not values:
        return None
    years = [int(match) for value in values for match in re.findall(r"(\d+)\s*년\s*미만", value)]
    prospective = any("예비" in value for value in values)
    if prospective and not years:
        return {"policy": "forbidden", "years": None, "name_restriction": False}
    if years:
        return {"policy": None if prospective else "required", "years": max(years), "name_restriction": False}
    return None


def normalize(item: dict, collected_at: str | None = None) -> dict | None:
    title = str(item.get("biz_pbanc_nm") or "").strip()
    if len(title) < 3:
        return None
    end = compact_date(item.get("pbanc_rcpt_end_dt"))
    if end and end < today_kst().isoformat():
        return None
    start = compact_date(item.get("pbanc_rcpt_bgng_dt"))
    serial = str(item.get("pbanc_sn") or title)
    url = (item.get("detl_pg_url") or item.get("biz_aply_url")
           or f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={serial}")
    if not str(url).startswith("http"):
        url = "https://" + str(url).lstrip("/")
    section = empty_section("tmp")
    targets = [value.strip() for value in re.split(r"[,，]", str(item.get("aply_trgt") or "")) if value.strip()]
    allowed = sorted({status for target in targets for status in PERSON_TARGETS.get(target, [])})
    target_evidence = f"신청 대상: {item.get('aply_trgt')}" + (f" — {item.get('aply_trgt_ctnt')}" if item.get("aply_trgt_ctnt") else "")
    if allowed:
        set_condition(section, "status", {"allowed": allowed, "excluded": None, "chip_mismatch": False}, target_evidence)
    elif targets:
        set_condition(section, "other_conditions", [f"신청 대상: {', '.join(targets)}"], target_evidence)
    age = _age_range(str(item.get("biz_trgt_age") or ""))
    if age == "gap":
        set_condition(section, "other_conditions", [f"대상 연령: {item.get('biz_trgt_age')}"], f"대상 연령: {item.get('biz_trgt_age')}")
    elif age:
        set_condition(section, "age", {**age, "basis_date": None}, f"대상 연령: {item.get('biz_trgt_age')}")
    business = _business(str(item.get("biz_enyy") or ""))
    if business:
        set_condition(section, "business_reg", business, f"창업 기간: {item.get('biz_enyy')}")
    region = str(item.get("supt_regin") or "").strip()
    if region and not re.search(r"전국", region):
        set_condition(section, "other_conditions", [f"지역 요건: {region}"], f"지역명: {region}")
    exclusion = short(item.get("aply_excl_trgt_ctnt"), 200)
    if exclusion and not re.fullmatch(r"(?:-|없음|해당\s*없음)", exclusion):
        set_condition(section, "other_conditions", ["신청 제외 대상 확인"], f"신청 제외 대상: {exclusion}")
    details = empty_details()
    details["schedule"] = [item for item in [schedule_item("apply", "접수", start, end, f"접수기간 {item.get('pbanc_rcpt_bgng_dt')}~{item.get('pbanc_rcpt_end_dt')}")] if item]
    methods = [str(item.get(key)).strip() for key in (
        "aply_mthd_onli_rcpt_istc", "aply_mthd_vst_rcpt_istc", "aply_mthd_pssr_rcpt_istc",
        "aply_mthd_fax_rcpt_istc", "aply_mthd_etc_istc") if item.get(key) and str(item.get(key)).strip() not in ("-", "")]
    if methods:
        details["apply_method"] = {"value": short(scrub(" · ".join(methods)), 240), "evidence": "K-Startup API 신청 방법"}
    details["summary"] = short(scrub(str(item.get("pbanc_ctnt") or "")), 400)
    if item.get("prfn_matr"):
        details["preference"] = short(item.get("prfn_matr"), 200)
    details["links"] = [link for link in (
        {"label": "K-Startup 공고", "url": url},
        {"label": "신청 페이지", "url": item.get("biz_aply_url")} if item.get("biz_aply_url") and item.get("biz_aply_url") != url else None,
        {"label": "사업 안내", "url": item.get("biz_gdnc_url")} if item.get("biz_gdnc_url") else None,
    ) if link]
    return make_contest(
        source_id=SOURCE["id"], source_name=SOURCE["name"], source_type=SOURCE["type"], key=serial, title=title,
        source_url=url, kind=kind_from_title(title, "support"),
        organizer=item.get("pbanc_ntrp_nm") or item.get("sprv_inst"), deadline=end,
        category=item.get("supt_biz_clsfc"), sections=[section], eligibility_known=True, details=details,
        collected_at=collected_at,
    )


def parse(payload) -> list[dict]:
    rows = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(rows, dict):
        rows = rows.get("data")
    if not isinstance(rows, list):
        raise http.SourceError("K-Startup 응답 형식이 예상과 다릅니다")
    return [contest for contest in (normalize(row) for row in rows if isinstance(row, dict)) if contest]


def fetch(env: dict) -> list[dict]:
    if http.mode() == "fixture":
        import json
        return parse(json.loads(http.fixture("kstartup.json")))
    key = env.get("DATA_GO_KR_SERVICE_KEY", "")
    found: dict[str, dict] = {}
    for page in (1, 2):
        payload = http.get_json(BASE, {
            "serviceKey": key, "page": page, "perPage": 100, "returnType": "json", "cond[rcrt_prgs_yn::EQ]": "Y",
        }, source="K-Startup API")
        for contest in parse(payload):
            found[contest["id"]] = contest
        total = payload.get("totalCount") if isinstance(payload, dict) else 0
        if not isinstance(total, int) or page * 100 >= total:
            break
    return list(found.values())
