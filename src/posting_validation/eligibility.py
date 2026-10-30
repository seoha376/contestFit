from __future__ import annotations

import re


PROFILES = [
    {"name": "① 만 24세 서울 거주 재학생 혼자", "age": 24, "region": "서울", "student_status": "재학생", "team_size": 1, "business_registered": False},
    {"name": "② 만 29세 직장인 혼자(사업자 없음)", "age": 29, "region": None, "student_status": "직장인", "team_size": 1, "business_registered": False},
    {"name": "③ 만 22세 휴학생 3인 팀", "age": 22, "region": None, "student_status": "휴학생", "team_size": 3, "business_registered": False},
    {"name": "④ 만 35세 사업자 보유자", "age": 35, "region": None, "student_status": "일반인", "team_size": 1, "business_registered": True},
]


def _condition(record: dict, name: str) -> tuple[object, object]:
    item = record.get(name) or {}
    return item.get("value"), item.get("evidence")


def _reason(field: str, message: str, evidence: object) -> dict:
    return {"field": field, "message": message, "evidence": evidence}


def decide_eligibility(record: dict, profile: dict) -> dict:
    failures: list[dict] = []
    unknowns: list[dict] = []
    matched: list[dict] = []

    age, age_evidence = _condition(record, "age")
    if age is None:
        unknowns.append(_reason("age", "연령 조건이 명시되지 않음", age_evidence))
    else:
        minimum = age.get("min") if isinstance(age, dict) else None
        maximum = age.get("max") if isinstance(age, dict) else None
        if minimum is not None and profile["age"] < minimum:
            failures.append(_reason("age", f"만 {minimum}세 이상 조건을 충족하지 못함", age_evidence))
        elif maximum is not None and profile["age"] > maximum:
            failures.append(_reason("age", f"만 {maximum}세 이하 조건을 충족하지 못함", age_evidence))
        else:
            matched.append(_reason("age", "연령 조건 충족", age_evidence))

    statuses, status_evidence = _condition(record, "student_status")
    if statuses is None:
        unknowns.append(_reason("student_status", "학적·신분 조건이 명시되지 않음", status_evidence))
    elif statuses == "제한없음":
        matched.append(_reason("student_status", "학적·신분 제한 없음", status_evidence))
    elif profile.get("student_status") is None:
        unknowns.append(_reason("student_status", "프로필의 학적·신분 정보가 없음", status_evidence))
    elif profile["student_status"] not in (statuses if isinstance(statuses, list) else [statuses]):
        failures.append(_reason("student_status", "허용된 학적·신분에 해당하지 않음", status_evidence))
    else:
        matched.append(_reason("student_status", "학적·신분 조건 충족", status_evidence))

    region, region_evidence = _condition(record, "region_restriction")
    if region is None:
        unknowns.append(_reason("region_restriction", "지역 조건이 명시되지 않음", region_evidence))
    elif region == "제한없음":
        matched.append(_reason("region_restriction", "지역 제한 없음", region_evidence))
    elif profile.get("region") is None:
        unknowns.append(_reason("region_restriction", "프로필의 거주 지역 정보가 없음", region_evidence))
    elif profile["region"] not in region:
        failures.append(_reason("region_restriction", "지역 조건을 충족하지 못함", region_evidence))
    else:
        matched.append(_reason("region_restriction", "지역 조건 충족", region_evidence))

    business, business_evidence = _condition(record, "business_registration")
    if business is None:
        unknowns.append(_reason("business_registration", "사업자 조건이 명시되지 않음", business_evidence))
    elif business == "필수" and not profile["business_registered"]:
        failures.append(_reason("business_registration", "사업자 등록 필수 조건을 충족하지 못함", business_evidence))
    elif business == "불가" and profile["business_registered"]:
        failures.append(_reason("business_registration", "사업자 보유자는 지원할 수 없음", business_evidence))
    else:
        matched.append(_reason("business_registration", "사업자 조건 충족", business_evidence))

    team_policy, team_evidence = _condition(record, "team_policy")
    if team_policy is None or team_policy == "미기재":
        unknowns.append(_reason("team_policy", "개인·팀 조건이 명시되지 않음", team_evidence))
    elif team_policy == "개인만" and profile["team_size"] != 1:
        failures.append(_reason("team_policy", "개인 참가만 허용됨", team_evidence))
    elif team_policy == "팀만" and profile["team_size"] <= 1:
        failures.append(_reason("team_policy", "팀 참가만 허용됨", team_evidence))
    else:
        matched.append(_reason("team_policy", "개인·팀 조건 충족", team_evidence))

    team_size, team_size_evidence = _condition(record, "team_size")
    team_text = str(team_size_evidence or team_size or "")
    range_match = re.search(r"(\d+)\s*[~\-–]\s*(\d+)\s*인", team_text)
    maximum_match = re.search(r"(\d+)\s*인\s*(?:이내|이하)", team_text)
    minimum_match = re.search(r"(\d+)\s*인\s*이상", team_text)
    if range_match and not (int(range_match.group(1)) <= profile["team_size"] <= int(range_match.group(2))):
        failures.append(_reason("team_size", f"{range_match.group(1)}~{range_match.group(2)}인 팀 조건을 충족하지 못함", team_size_evidence))
    elif maximum_match and profile["team_size"] > int(maximum_match.group(1)):
        failures.append(_reason("team_size", f"{maximum_match.group(1)}인 이하 팀 조건을 충족하지 못함", team_size_evidence))
    elif minimum_match and profile["team_size"] < int(minimum_match.group(1)):
        failures.append(_reason("team_size", f"{minimum_match.group(1)}인 이상 팀 조건을 충족하지 못함", team_size_evidence))

    other, other_evidence = _condition(record, "other_conditions")
    if other:
        unknowns.append(_reason("other_conditions", "추가 조건은 프로필만으로 자동 판정할 수 없음", other_evidence))

    if failures:
        return {"profile": profile["name"], "result": "지원 불가", "reasons": failures}
    if unknowns:
        return {"profile": profile["name"], "result": "확인 필요", "reasons": unknowns}
    return {"profile": profile["name"], "result": "지원 가능", "reasons": matched}
