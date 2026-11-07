from __future__ import annotations

import re


CONFIDENCE_FIELDS = [
    "age", "status", "major_scope", "region", "nationality",
    "business_reg", "entry_type", "team_size", "other_conditions",
]


def _field(record: dict, name: str, override: dict | None = None) -> dict:
    if override is not None and name in override:
        return override[name]
    return record.get(name) or {"value": None, "evidence": None}


def _value(record: dict, name: str, override: dict | None = None):
    return _field(record, name, override).get("value")


def _evidence(record: dict, name: str, override: dict | None = None):
    return _field(record, name, override).get("evidence")


def _status(record: dict, override: dict | None = None) -> dict:
    source = _field(record, "student_status", override)
    current = source.get("value")
    if current == "제한없음":
        allowed, excluded = [], []
    elif isinstance(current, list):
        allowed, excluded = current, None
    elif current is not None:
        allowed, excluded = [current], None
    else:
        allowed, excluded = None, None
    return {"allowed": allowed, "excluded": excluded, "chip_mismatch": bool(source.get("chip_mismatch"))}


def _business_registration(record: dict, override: dict | None = None) -> dict:
    source = _field(record, "business_registration", override)
    value = source.get("value")
    evidence = str(source.get("evidence") or "")
    policy = {"필수": "required", "필요": "required", "불가": "forbidden", "연차": "years", "무관": "any"}.get(value)
    years = source.get("years")
    if years is None:
        match = re.search(r"창업\s*(\d+)\s*년\s*미만", evidence)
        years = int(match.group(1)) if match else None
    name_restriction = bool(source.get("name_restriction")) or bool(re.search(r"(?:사업자|법인|단체).{0,12}명의\s*불가", evidence))
    if name_restriction and value == "불가":
        policy = "any"
    return {"policy": policy, "years": years, "name_restriction": name_restriction}


def _team_size(record: dict, override: dict | None = None):
    value = _value(record, "team_size", override)
    if isinstance(value, dict):
        return {"min": value.get("min"), "max": value.get("max")}
    evidence = _evidence(record, "team_size", override)
    text = " ".join(str(item) for item in evidence) if isinstance(evidence, list) else str(evidence or value or "")
    if re.search(r"1\s*인\s*\(\s*또는\s*팀\s*\)", text):
        return None
    range_match = re.search(r"(\d+)\s*[~\-–]\s*(\d+)\s*인", text)
    if range_match:
        return {"min": int(range_match.group(1)), "max": int(range_match.group(2))}
    max_match = re.search(r"(?:최대\s*)?(\d+)\s*인\s*(?:이내|이하)|최대\s*(\d+)\s*인", text)
    if max_match:
        return {"min": None, "max": int(max_match.group(1) or max_match.group(2))}
    min_match = re.search(r"(\d+)\s*인\s*이상", text)
    if min_match:
        return {"min": int(min_match.group(1)), "max": None}
    exact_match = re.search(r"(\d+)\s*인(?:이|으로)\s*(?:1\s*)?팀", text)
    if exact_match:
        size = int(exact_match.group(1))
        return {"min": size, "max": size}
    return None


def _entry_type(record: dict, override: dict | None = None):
    return {"개인만": "individual", "팀만": "team", "둘다": "both"}.get(_value(record, "team_policy", override))


def _section(record: dict, override: dict | None, index: int) -> dict:
    age = _value(record, "age", override)
    status_source = _field(record, "student_status", override)
    evidence = {
        "age": _evidence(record, "age", override),
        "status": status_source.get("evidence"),
        "major_scope": _evidence(record, "major_scope", override),
        "region": _evidence(record, "region_restriction", override),
        "nationality": _evidence(record, "nationality", override),
        "business_reg": _evidence(record, "business_registration", override),
        "entry_type": _evidence(record, "team_policy", override),
        "team_size": _evidence(record, "team_size", override),
        "other_conditions": _evidence(record, "other_conditions", override),
    }
    return {
        "id": f"{record['id']}-section-{index}",
        "name": (override or {}).get("name"),
        "age": {
            "min": age.get("min") if isinstance(age, dict) else None,
            "max": age.get("max") if isinstance(age, dict) else None,
            "basis_date": None,
        },
        "status": _status(record, override),
        "major_scope": _value(record, "major_scope", override),
        "region": _value(record, "region_restriction", override),
        "nationality": _value(record, "nationality", override),
        "business_reg": _business_registration(record, override),
        "entry_type": _entry_type(record, override),
        "team_size": _team_size(record, override),
        "other_conditions": _value(record, "other_conditions", override) or [],
        "evidence": evidence,
        "evidence_source": {name: "body" if value else None for name, value in evidence.items()},
        "chip_evidence": {"status": status_source.get("chip_evidence")},
        "confidence": {name: None for name in CONFIDENCE_FIELDS},
    }


def convert_records(records: list[dict], collected_at: str) -> dict:
    contests = []
    for record in records:
        overrides = record.get("sections") or [None]
        contests.append({
            "id": record["id"],
            "title": _value(record, "title"),
            "organizer": _value(record, "organizer"),
            "deadline": _value(record, "deadline"),
            "category": None,
            "topic_tags": [],
            "skill_signals": [],
            "source_url": record.get("source_url"),
            "collected_at": collected_at,
            "is_sample": True,
            "validation_status": "unverified",
            "sections": [_section(record, override, index) for index, override in enumerate(overrides, start=1)],
        })
    return {
        "schema_version": "1.1",
        "generated_from": "extracted_eligibility.json",
        "validation_status": "unverified",
        "contests": contests,
    }
