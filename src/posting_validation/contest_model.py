"""Shared builders for the contest schema consumed by web/decision-engine.mjs.

Every source adapter, the URL preview and the seed converter produce the same
shape so the browser judges all postings with one engine. Values stay ``None``
unless the source states them; unknown eligibility is flagged, never guessed.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
CONDITION_FIELDS = (
    "age", "status", "major_scope", "region", "nationality",
    "business_reg", "entry_type", "team_size", "other_conditions",
)
KINDS = ("contest", "competition", "support", "internship")
KIND_LABELS = {"contest": "공모전", "competition": "대회", "support": "지원사업", "internship": "인턴"}
MAX_EVIDENCE = 300


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def today_kst() -> date:
    return datetime.now(KST).date()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def short(value, limit: int = MAX_EVIDENCE) -> str | None:
    """Keep evidence to a short excerpt; full posting text is never stored."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def compact_date(value) -> str | None:
    """Parse yyyyMMdd, yyyy-MM-dd, yy-MM-dd, yyyy.MM.dd or ISO timestamps to YYYY-MM-DD."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})T", text)
    if iso:
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=UTC)
            return moment.astimezone(KST).date().isoformat()
        except ValueError:
            return None
    patterns = (
        r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)",
        r"(?<!\d)(\d{4})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})",
        r"(?<!\d)(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})(?!\d)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def empty_section(contest_id: str, index: int = 1, name: str | None = None) -> dict:
    return {
        "id": f"{contest_id}-section-{index}",
        "name": name,
        "age": {"min": None, "max": None, "basis_date": None},
        "status": {"allowed": None, "excluded": None, "chip_mismatch": False},
        "major_scope": None,
        "region": None,
        "nationality": None,
        "business_reg": {"policy": None, "years": None, "name_restriction": False},
        "entry_type": None,
        "team_size": None,
        "other_conditions": [],
        "evidence": {field: None for field in CONDITION_FIELDS},
        "evidence_source": {field: None for field in CONDITION_FIELDS},
        "chip_evidence": {"status": None},
        "confidence": {field: None for field in CONDITION_FIELDS},
    }


def set_condition(section: dict, field: str, value, evidence, source: str = "api") -> None:
    """Store a condition with its short evidence; the engine needs both to rule out an applicant."""
    excerpt = [short(item) for item in evidence if short(item)] if isinstance(evidence, list) else short(evidence)
    if field == "other_conditions":
        section["other_conditions"] = list(dict.fromkeys([*section["other_conditions"], *value]))
        existing = section["evidence"].get("other_conditions") or []
        existing = existing if isinstance(existing, list) else [existing]
        additions = excerpt if isinstance(excerpt, list) else [excerpt]
        section["evidence"]["other_conditions"] = [item for item in dict.fromkeys([*existing, *additions]) if item]
    else:
        section[field] = value
        section["evidence"][field] = excerpt
    section["evidence_source"][field] = source


def has_conditions(section: dict) -> bool:
    age = section.get("age") or {}
    status = section.get("status") or {}
    business = section.get("business_reg") or {}
    return any((
        age.get("min") is not None, age.get("max") is not None,
        status.get("allowed") is not None, status.get("excluded") is not None,
        section.get("major_scope"), section.get("region"), section.get("nationality"),
        business.get("policy") is not None, business.get("years") is not None,
        section.get("entry_type"), section.get("team_size"), section.get("other_conditions"),
    ))


def schedule_item(kind: str, label: str, start: str | None, end: str | None = None, evidence=None) -> dict | None:
    if not start and not end:
        return None
    return {"type": kind, "label": label, "date": start or end, "end_date": end if start and end and end != start else None,
            "evidence": short(evidence, 200)}


def empty_details() -> dict:
    return {
        "schedule": [], "deliverables": [], "apply_method": None, "reward": None,
        "entry_fee": None, "rights": None, "summary": None, "links": [],
    }


def make_contest(*, source_id: str, source_name: str, source_type: str, key: str, title: str,
                 source_url: str, kind: str, organizer: str | None = None, deadline: str | None = None,
                 category: str | None = None, sections: list[dict] | None = None,
                 eligibility_known: bool = False, details: dict | None = None,
                 collected_at: str | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind}")
    contest_id = stable_id(source_id, key)
    built_sections = sections or [empty_section(contest_id)]
    for index, section in enumerate(built_sections, 1):
        section["id"] = f"{contest_id}-section-{index}"
    return {
        "id": contest_id,
        "title": short(title, 200) or "제목 확인 필요",
        "organizer": short(organizer, 120),
        "deadline": deadline,
        "category": short(category, 60),
        "topic_tags": [],
        "skill_signals": [],
        "source_url": source_url,
        "collected_at": collected_at or now_iso(),
        "is_sample": False,
        "validation_status": "unverified",
        "kind": kind,
        "source": {"id": source_id, "name": source_name, "type": source_type},
        "eligibility_known": eligibility_known,
        "sections": built_sections,
        "details": details or empty_details(),
    }


def kind_from_title(title: str, default: str) -> str:
    if re.search(r"인턴", title):
        return "internship"
    if re.search(r"공모전|아이디어\s*공모|콘테스트|contest", title, re.I):
        return "contest"
    if re.search(r"경진대회|대회|챌린지|해커톤|해카톤|hackathon|CTF|competition", title, re.I):
        return "competition"
    return default
