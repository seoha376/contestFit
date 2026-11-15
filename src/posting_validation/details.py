"""Extract schedule, deliverables and application details from posting text.

Each value keeps a short evidence excerpt so the detail page can show where it
came from. Dates without a year borrow the posting's year only when a full date
appears earlier in the same text; otherwise the item is skipped, not guessed.
"""

from __future__ import annotations

import re
from datetime import date

from .contest_model import empty_details, schedule_item, short


FULL_DATE = re.compile(r"(?<!\d)(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*(?:일)?")
SHORT_DATE = re.compile(r"(?<![\d.])(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*(?:일)?(?![\d])")
SCHEDULE_LABELS = (
    ("apply", r"접수\s*기간|모집\s*기간|공모\s*기간|신청\s*기간|응모\s*기간|참가\s*신청|등록\s*기간|제출\s*기간|접수\s*마감|신청\s*마감"),
    ("review", r"서류\s*심사|1차\s*심사|예선|온라인\s*심사|심사\s*기간|평가\s*기간"),
    ("event", r"본선|결선|발표\s*평가|대회\s*일[시정자]|행사\s*일[시정자]|해커톤\s*일[시정자]|교육\s*기간|활동\s*기간|진행\s*기간"),
    ("announcement", r"(?:최종\s*)?(?:결과|수상자?|선정)\s*발표|합격자\s*발표|발표\s*일"),
    ("award", r"시상식|시상\s*일"),
)
LABEL_TEXT = {"apply": "접수", "review": "심사", "event": "본선·행사", "announcement": "결과 발표", "award": "시상식"}
DELIVERABLE_HEADER = re.compile(r"^(?:[-●■□○◆▶※*·\d.)\s]*)?(제출\s*서류|제출\s*물|제출\s*자료|제출\s*형식|응모\s*작품?|출품\s*작|작품\s*규격|접수\s*서류|구비\s*서류|제출\s*방법\s*및\s*서류)")
APPLY_HEADER = re.compile(r"(접수\s*방법|응모\s*방법|신청\s*방법|참가\s*방법|지원\s*방법|제출\s*방법)")
STOP_HEADER = re.compile(r"^(?:[-●■□○◆▶※*·\d.)\s]*)?(시상|상금|심사|유의\s*사항|문의|일정|접수\s*기간|공모\s*일정|참가\s*자격|응모\s*자격|저작권|주최|주관|후원)")
REWARD_PATTERNS = (
    re.compile(r"(총\s*상금)[^\n\d]{0,20}(\d[\d,.]*\s*(?:억|천만|백만|만)?\s*원)"),
    re.compile(r"(상금|시상\s*규모|시상\s*내역|부상)[^\n]{0,40}?(\d[\d,.]*\s*(?:억|천만|백만|만)?\s*원)"),
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")
LABELED_LINE = re.compile(r"^[가-힣A-Za-z ]{2,12}\s*[:：]")
FEE = re.compile(r"참가비[^\n]{0,30}")
RIGHTS = re.compile(r"[^\n]{0,30}(저작권|지식재산권|소유권|사용권)[^\n]{0,60}")


def scrub(value: str) -> str:
    """Drop contact addresses; ContestFit stores no e-mail or phone numbers."""
    return PHONE.sub("[연락처 생략]", EMAIL.sub("[이메일 생략]", value))


def _lines(text: str) -> list[str]:
    return [scrub(line.strip()) for line in str(text or "").splitlines() if line.strip()]


def _dates_in(line: str, default_year: int | None) -> list[str]:
    found: list[tuple[int, str]] = []
    year = default_year
    for match in FULL_DATE.finditer(line):
        y, m, d = (int(part) for part in match.groups())
        try:
            found.append((match.start(), date(y, m, d).isoformat()))
            year = y
        except ValueError:
            continue
    covered = [match.span() for match in FULL_DATE.finditer(line)]
    for match in SHORT_DATE.finditer(line):
        if any(start <= match.start() < end for start, end in covered) or year is None:
            continue
        # Ignore times such as 18:00 and fractions such as 1/2.
        tail = line[match.end():match.end() + 1]
        if tail in (":",):
            continue
        m, d = (int(part) for part in match.groups())
        if not 1 <= m <= 12:
            continue
        try:
            value = date(year, m, d)
        except ValueError:
            continue
        if found and value.isoformat() < found[-1][1]:
            # A range such as 12.20 ~ 1.15 crosses the year; do not guess.
            continue
        found.append((match.start(), value.isoformat()))
    return [value for _, value in sorted(found)]


def _first_year(text: str) -> int | None:
    match = FULL_DATE.search(text)
    return int(match.group(1)) if match else None


def extract_schedule(text: str) -> list[dict]:
    lines = _lines(text)
    default_year = _first_year(text)
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, line in enumerate(lines):
        for kind, pattern in SCHEDULE_LABELS:
            if not re.search(pattern, line):
                continue
            candidates = [line] + ([lines[index + 1]] if index + 1 < len(lines) else [])
            dates: list[str] = []
            evidence = line
            for candidate in candidates:
                dates = _dates_in(candidate, default_year)
                if dates:
                    evidence = line if candidate == line else f"{line} {candidate}"
                    break
            if not dates:
                continue
            start, end = dates[0], dates[-1] if len(dates) > 1 else None
            if kind == "apply" and re.search(r"마감", line) and len(dates) == 1:
                start, end = None, dates[0]
            key = (kind, start or end or "")
            if key in seen:
                break
            seen.add(key)
            item = schedule_item(kind, LABEL_TEXT[kind], start, end, evidence)
            if item:
                items.append(item)
            break
    return sorted(items, key=lambda item: item["date"])


def _collect_block(lines: list[str], index: int, header: re.Pattern) -> list[str]:
    line = lines[index]
    inline = re.split(r"\s*[:：]\s*", line, maxsplit=1)
    values: list[str] = []
    if len(inline) == 2 and len(inline[1].strip()) > 1:
        values.extend(part.strip() for part in re.split(r"\s*(?:,|/|및)\s*(?![^(]*\))", inline[1]) if part.strip())
    for candidate in lines[index + 1:index + 10]:
        if STOP_HEADER.search(candidate) or header.search(candidate) and candidate != line:
            break
        if LABELED_LINE.search(candidate) and not re.match(r"^[-●■□○◆▶※*·]|^\d+[.)]|^[①-⑳]", candidate):
            break
        cleaned = re.sub(r"^[-●■□○◆▶※*·]\s*|^\d+[.)]\s*|^[①-⑳]\s*", "", candidate).strip()
        if not cleaned or len(cleaned) > 160:
            continue
        values.append(cleaned)
        if len(values) >= 8:
            break
    return values


def extract_deliverables(text: str) -> list[dict]:
    lines = _lines(text)
    items: list[dict] = []
    for index, line in enumerate(lines):
        if not DELIVERABLE_HEADER.search(line):
            continue
        for value in _collect_block(lines, index, DELIVERABLE_HEADER):
            if any(value == item["text"] for item in items):
                continue
            items.append({"text": short(value, 160), "evidence": short(line if value in line else f"{line} {value}", 200)})
        if items:
            break
    return items[:8]


def extract_apply_method(text: str) -> dict | None:
    lines = _lines(text)
    for index, line in enumerate(lines):
        if not APPLY_HEADER.search(line):
            continue
        values = _collect_block(lines, index, APPLY_HEADER)
        if values:
            value = " · ".join(values[:4])
            return {"value": short(value, 240), "evidence": short(line, 200)}
    return None


def extract_reward(text: str) -> dict | None:
    match = next((found for pattern in REWARD_PATTERNS if (found := pattern.search(text))), None)
    if not match:
        return None
    line = next((line for line in _lines(text) if match.group(2) in line), match.group(0))
    return {"value": short(f"{re.sub(r'\s+', ' ', match.group(1))} {match.group(2)}", 80), "evidence": short(line, 200)}


def extract_details(text: str) -> dict:
    details = empty_details()
    details["schedule"] = extract_schedule(text)
    details["deliverables"] = extract_deliverables(text)
    details["apply_method"] = extract_apply_method(text)
    details["reward"] = extract_reward(text)
    text = scrub(str(text or ""))
    fee = FEE.search(text)
    if fee:
        details["entry_fee"] = {"value": "무료" if re.search(r"무료|없음", fee.group(0)) else short(fee.group(0), 80), "evidence": short(fee.group(0), 200)}
    rights = RIGHTS.search(text)
    if rights:
        details["rights"] = {"value": short(rights.group(0), 120), "evidence": short(rights.group(0), 200)}
    return details


def merge_details(base: dict | None, extra: dict | None) -> dict:
    """Fill gaps in API-provided details with page-extracted ones without overwriting."""
    merged = {**empty_details(), **(base or {})}
    extra = extra or {}
    merged["schedule"] = list(merged["schedule"])
    known = {(item["type"], item["date"]) for item in merged["schedule"]}
    for item in extra.get("schedule", []):
        if (item["type"], item["date"]) in known:
            continue
        if item["type"] == "apply":
            existing = next((entry for entry in merged["schedule"] if entry["type"] == "apply"), None)
            if existing:
                # A full start~end range from the page beats an end-only list entry.
                if item.get("end_date") and not existing.get("end_date"):
                    merged["schedule"][merged["schedule"].index(existing)] = item
                continue
        merged["schedule"].append(item)
    merged["schedule"].sort(key=lambda item: item["date"])
    if not merged["deliverables"]:
        merged["deliverables"] = extra.get("deliverables", [])
    for key in ("apply_method", "reward", "entry_fee", "rights", "summary"):
        if not merged.get(key) and extra.get(key):
            merged[key] = extra[key]
    links = {link["url"]: link for link in [*merged.get("links", []), *extra.get("links", [])] if link.get("url")}
    merged["links"] = list(links.values())
    return merged
