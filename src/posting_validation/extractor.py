from __future__ import annotations

import re

from .parser import DATE_RE, normalize_space, parse_deadline

COMMON_FIELDS = ["type", "title", "organizer", "deadline", "region", "eligibility", "participation_form", "team_size", "onsite_required", "reward", "period"]
TYPE_FIELDS = {
    "공모전": [
        "deliverable_type", "rights_clause", "entry_fee", "submission_format",
        "age", "student_status", "region_restriction", "business_registration",
        "nationality", "major_scope", "team_policy", "other_conditions",
    ],
    "대외활동": ["activity_period", "weekly_hours", "stipend"],
    "인턴": ["job_role", "employment_type", "workplace", "pay"],
}
ALL_TYPE_FIELDS = [field for fields in TYPE_FIELDS.values() for field in fields]


def classify_domain(text: str) -> str:
    buckets = [
        ("IT/데이터", r"AI|인공지능|데이터|개발|소프트웨어|코딩|해커톤"),
        ("마케팅/콘텐츠", r"마케팅|브랜드|콘텐츠|SNS|홍보|미디어"),
        ("디자인/예술", r"디자인|영상|사진|예술|웹툰|일러스트"),
        ("환경/사회", r"환경|ESG|사회공헌|봉사|기후|복지"),
        ("경영/금융", r"경영|금융|경제|창업|투자|회계"),
        ("과학/공학", r"과학|공학|연구|반도체|로봇|바이오"),
    ]
    for name, pattern in buckets:
        if re.search(pattern, text, re.I):
            return name
    return "기타"


def posting_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return None
    return normalize_space(re.sub(r"\s*\|\s*공모전 대외활동-링커리어.*$", "", match.group(1)))


def field(value=None, evidence=None, **metadata) -> dict:
    return {"value": value, "evidence": evidence, **metadata}


def lines(text: str) -> list[str]:
    result = []
    for line in text.splitlines():
        normalized = normalize_space(line)
        if normalized:
            result.append(normalized)
    return result


def first_line(text: str, patterns: list[str]) -> str | None:
    for line in lines(text):
        if any(re.search(pattern, line, re.I) for pattern in patterns):
            return line
    return None


def main_posting_text(text: str) -> str:
    markers = ("허위·과장·오류 내용이 있다면 신고해주세요", "허위·과장·오류 내용이 있다면")
    end = min((text.find(marker) for marker in markers if marker in text), default=len(text))
    return text[:end].rstrip()


def labeled_value(line: str | None) -> str | None:
    if not line:
        return None
    parts = re.split(r"\s*[:：]\s*", line, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 and parts[1].strip() else line.strip()


def _header_organizer(text: str, title: str | None) -> dict:
    if not title:
        return field()
    text_lines = lines(text)
    for index in range(len(text_lines) - 2, -1, -1):
        if text_lines[index] == title and index + 2 < len(text_lines) and "모집글 보기" in text_lines[index + 2]:
            value = text_lines[index + 1]
            return field(value, value)
    return field()


def _compact_value(text: str, label: str, stop_labels: list[str]) -> dict:
    stop = "|".join(map(re.escape, stop_labels))
    pattern = rf"{re.escape(label)}(.+?)(?={stop}|$)"
    for line in lines(text):
        match = re.search(pattern, line)
        if match and match.group(1).strip():
            return field(match.group(1).strip(), line)
    return field()


def _region_field(text: str) -> dict:
    text_lines = lines(text)
    for index, line in enumerate(text_lines):
        match = re.search(r"(?:활동지역|근무지역)\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if not value and index + 1 < len(text_lines):
            value = text_lines[index + 1]
            return field(value, f"{line}\n{value}")
        if value:
            return field(value, line)
    return field()


def _period_field(text: str) -> dict:
    text_lines = lines(text)
    for index, line in enumerate(text_lines):
        start = re.search(r"시작일\s*(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})", line)
        if not start:
            continue
        for end_line in text_lines[index + 1:index + 3]:
            end = re.search(r"마감일\s*(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})", end_line)
            if end:
                label_line = text_lines[index - 1] if index else "접수기간"
                evidence = f"{label_line}\n{line}\n{end_line}"
                return field(f"{start.group(1)} ~ {end.group(1)}", evidence)
    for index, line in enumerate(text_lines):
        if not re.search(r"접수기간|모집기간|공모기간", line):
            continue
        if DATE_RE.search(line):
            return field(labeled_value(line), line)
        if index + 1 < len(text_lines) and not text_lines[index + 1].startswith("시작일") and re.search(r"\d{2,4}[.년/-]\s*\d{1,2}", text_lines[index + 1]):
            value = text_lines[index + 1]
            return field(value, f"{line}\n{value}")
    return field()


def _direct_deadline_range_evidence(text: str) -> str | None:
    text_lines = lines(text)
    for index, line in enumerate(text_lines):
        if not re.search(r"접수기간|모집기간|공모기간", line):
            continue
        candidates = [line]
        if index + 1 < len(text_lines):
            candidates.append(text_lines[index + 1])
        evidence = "\n".join(candidates)
        if len(DATE_RE.findall(evidence)) >= 2:
            return evidence
    return None


def _deadline_from_evidence(evidence: str):
    """Use an abbreviated range end only when its year is unambiguous."""
    dates = list(DATE_RE.finditer(evidence))
    if len(dates) == 1:
        year, start_month, start_day = map(int, dates[0].groups())
        remainder = evidence[dates[0].end():]
        abbreviated_end = re.match(r"^\s*\.?\s*[~–-]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})(?:일)?", remainder)
        if abbreviated_end:
            end_month, end_day = map(int, abbreviated_end.groups())
            if (end_month, end_day) < (start_month, start_day):
                return None
            return parse_deadline(f"마감일 {year}-{end_month:02d}-{end_day:02d}")
    return parse_deadline(evidence)


def _submission_format_field(text: str) -> dict:
    text_lines = lines(text)
    for index, line in enumerate(text_lines):
        if re.search(r"제출\s*형식|작품\s*규격|파일\s*규격|제출물", line):
            inline = re.split(r"\s*[:：]\s*", line, maxsplit=1)
            if len(inline) == 2 and re.search(r"PDF|HWP|DOCX?|PPTX?|MP4|JPE?G|PNG|A4|\d+\s*(?:쪽|페이지|MB|GB|초|분)|픽셀|해상도", inline[1], re.I):
                return field(inline[1].strip(), line)
            values: list[str] = []
            evidence: list[str] = []
            for candidate in text_lines[index + 1:index + 12]:
                if re.search(r"^(?:[-●■※]\s*)?(?:제출서류|접수\s*방법|유의\s*사항|시상\s*내역|문의\s*사항|공모\s*일정)", candidate):
                    break
                if re.search(r"PDF|HWP|DOCX?|PPTX?|MP4|JPE?G|PNG|A4|\d+\s*(?:쪽|페이지|MB|GB|초|분)|픽셀|해상도|화면\s*비율|가로형|세로형|분량|파일", candidate, re.I):
                    values.append(re.sub(r"^[-●■※]\s*", "", candidate).strip())
                    evidence.append(candidate)
            if values:
                return field("; ".join(values), evidence[0] if len(evidence) == 1 else evidence)
    return field()


def _age_field(text: str) -> dict:
    for line in lines(text):
        if not re.search(r"(?:만\s*)?\d{1,2}\s*세", line):
            continue
        if re.search(r"법정대리인.{0,30}(?:동의|서명)|(?:동의|서명).{0,30}법정대리인", line):
            continue
        minimum = None
        maximum = None
        for number, bound in re.findall(r"(?:만\s*)?(\d{1,2})\s*세\s*(이상|이하|미만|초과)", line):
            value = int(number)
            if bound == "이상":
                minimum = value
            elif bound == "초과":
                minimum = value + 1
            elif bound == "이하":
                maximum = value
            elif bound == "미만":
                maximum = value - 1
        if minimum is not None or maximum is not None:
            return field({"min": minimum, "max": maximum}, line)
    return field()


def _target_chip(text: str) -> tuple[str | None, str | None]:
    for line in lines(text):
        match = re.search(r"기업형태.*?참여대상(.+?)(?=시상규모|접수기간|$)", line)
        if match:
            return match.group(1).strip(), line
    return None, None


def _status_values(text: str) -> list[str]:
    statuses: list[str] = []
    mappings = [
        ("재학생", r"재학생|(?<!원)대학생|대학\(원\)생"),
        ("휴학생", r"휴학생"),
        ("대학원생", r"대학원생|대학\(원\)생"),
        ("수료생", r"수료생"),
        ("직장인", r"직장인"),
        ("일반인", r"일반인"),
        ("졸업생", r"졸업생"),
        ("예비창업자", r"예비\s*창업자"),
    ]
    for value, pattern in mappings:
        if re.search(pattern, text) and value not in statuses:
            statuses.append(value)
    return statuses


def _student_status_field(text: str) -> dict:
    chip_value, chip_evidence = _target_chip(text)
    unrestricted = None
    best: tuple[list[str], str] | None = None
    for line in lines(text):
        if line == chip_evidence or re.search(r"학교,\s*전공,\s*연령|합격.*자소서", line):
            continue
        if re.search(r"대상\s*제한\s*없음|학력\s*무관", line) or (
            re.search(r"누구나|모두\s*환영", line) and not re.search(r"(?:에\s*한함|한정|만\s*참가|만\s*지원)", line)
        ):
            unrestricted = unrestricted or line
            continue
        if not re.search(r"재학생|휴학생|대학(?:\(원\)|원)?생|직장인|일반인|졸업생|수료생|예비\s*창업자", line):
            continue
        statuses = _status_values(line)
        if statuses and (best is None or len(statuses) >= len(best[0])):
            best = (statuses, line)
    chip_unrestricted = bool(chip_value and re.search(r"대상\s*제한\s*없음", chip_value))
    if best:
        chip_statuses = _status_values(chip_value or "")
        mismatch = chip_unrestricted or (bool(chip_statuses) and set(chip_statuses) != set(best[0]))
        return field(best[0], best[1], chip_mismatch=mismatch, chip_evidence=chip_evidence)
    if unrestricted:
        return field("제한없음", unrestricted, chip_mismatch=bool(chip_value and not chip_unrestricted), chip_evidence=chip_evidence)
    return field(None, None, chip_mismatch=False, chip_evidence=chip_evidence)


def _region_restriction_field(text: str) -> dict:
    regions = [
        ("서울", r"서울(?:특별시)?"), ("부산", r"부산(?:광역시)?"), ("대구", r"대구(?:광역시)?"),
        ("인천", r"인천(?:광역시)?"), ("광주", r"광주(?:광역시)?"), ("대전", r"대전(?:광역시)?"),
        ("울산", r"울산(?:광역시)?"), ("세종", r"세종(?:특별자치시)?"), ("경기", r"경기(?:도)?"),
        ("강원", r"강원(?:특별자치도|도)?"), ("충북", r"충청북도|충북"), ("충남", r"충청남도|충남"),
        ("전북", r"전북특별자치도|전라북도|전북"), ("전남", r"전라남도|전남"),
        ("경북", r"경상북도|경북"), ("경남", r"경상남도|경남"), ("제주", r"제주특별자치도|제주"),
    ]
    for line in lines(text):
        if re.search(r"지역\s*(?:제한)?\s*(?:없음|무관)|전국\s*(?:누구나|민)|누구나", line):
            continue
        basis = None
        if re.search(r"거주|주민등록", line):
            basis = "residence"
        elif re.search(r"(?:학교|대학).{0,15}소재|소재.{0,15}(?:학교|대학)", line):
            basis = "school"
        elif re.search(r"소속기관.{0,15}소재|소재.{0,15}소속기관", line):
            basis = "affiliation"
        if basis is None:
            continue
        found = [name for name, pattern in regions if re.search(pattern, line)]
        if found:
            return field({"regions": found, "basis": basis}, line)
    return field()


def _business_registration_field(text: str) -> dict:
    for line in lines(text):
        if not re.search(r"사업자|법인|창업", line):
            continue
        if re.search(r"(?:사업자|법인|단체).{0,12}명의\s*불가", line):
            return field("무관", line, years=None, name_restriction=True)
        years = re.search(r"창업\s*(\d+)\s*년\s*미만", line)
        if years:
            return field("연차", line, years=int(years.group(1)), name_restriction=False)
        if re.search(r"사업자.{0,15}(?:없는|미등록|보유하지)|사업자\s*등록\s*불가", line):
            return field("불가", line, years=None, name_restriction=False)
        if re.search(r"사업자.{0,15}(?:필수|등록자|보유자)|사업체", line):
            return field("필요", line, years=None, name_restriction=False)
        if re.search(r"무관|제한\s*없음", line):
            return field("무관", line, years=None, name_restriction=False)
    return field(None, None, years=None, name_restriction=False)


def _nationality_field(text: str) -> dict:
    for line in lines(text):
        if re.search(r"대한민국\s*(?:국민|국적)|한국\s*국적|내국인", line):
            return field("대한민국", line)
        if re.search(r"외국인.{0,12}(?:가능|포함)|국적\s*(?:제한\s*)?(?:없음|무관)", line):
            return field("제한없음", line)
    return field()


def _major_scope_field(text: str) -> dict:
    for line in lines(text):
        if re.search(r"학교,\s*전공,\s*연령|합격.*자소서", line):
            continue
        match = re.search(r"([가-힣A-Za-z·/ ]{1,30}(?:관련\s*)?전공)(?:자|생|에\s*한함|만)?", line)
        if match and re.search(r"지원|참가|자격|대상|전공자|전공생|전공에", line):
            return field(normalize_space(match.group(1)), line)
    return field()


def _team_policy_field(text: str) -> dict:
    both = first_line(text, [r"개인.{0,25}(?:또는|및|/).{0,25}팀", r"개인.{0,25}(?:최대\s*)?\d+\s*인.{0,10}팀", r"혼자도.{0,30}팀"])
    if both:
        return field("둘다", both)
    individual = first_line(text, [r"개인\s*(?:자격|만|으로만|참가|지원)", r"팀\s*(?:참가|지원)\s*불가"])
    if individual:
        return field("개인만", individual)
    team = first_line(text, [r"\d+\s*[~\-–]\s*\d+\s*인.{0,12}(?:팀|1팀)", r"팀\s*(?:으로만|단위|참가|지원)", r"개인\s*(?:참가|지원)\s*불가"])
    if team:
        return field("팀만", team)
    return field()


def _team_size_field(text: str) -> dict:
    for line in lines(text):
        if re.search(r"1\s*인\s*\(\s*또는\s*팀\s*\)", line):
            continue
        range_match = re.search(r"(\d+)\s*[~\-–]\s*(\d+)\s*인", line)
        if range_match:
            return field({"min": int(range_match.group(1)), "max": int(range_match.group(2))}, line)
        max_match = re.search(r"(?:최대\s*)?(\d+)\s*인\s*(?:이내|이하)|최대\s*(\d+)\s*인", line)
        if max_match:
            maximum = int(max_match.group(1) or max_match.group(2))
            return field({"min": None, "max": maximum}, line)
        min_match = re.search(r"(\d+)\s*인\s*이상", line)
        if min_match:
            return field({"min": int(min_match.group(1)), "max": None}, line)
        exact_match = re.search(r"(\d+)\s*인(?:이|으로)\s*(?:1\s*)?팀", line)
        if exact_match:
            size = int(exact_match.group(1))
            return field({"min": size, "max": size}, line)
    return field()


def _section_overrides(text: str) -> list[dict]:
    candidates: list[tuple[str, str]] = []
    for line in lines(text):
        match = re.match(r"^[-●■※\s]*(.+?(?:부문|트랙))\s*[:：]\s*(.+)$", line)
        if not match:
            continue
        description = match.group(2).strip()
        if re.search(r"개인|팀|기관|대학|학생|직장인|일반인|창업자|거주|국민|전공", description):
            candidates.append((match.group(1).strip(), description))
    if len(candidates) < 2:
        return []
    result = []
    for name, description in candidates:
        section = {
            "name": name,
            "age": _age_field(description),
            "student_status": _student_status_field(description),
            "region_restriction": _region_restriction_field(description),
            "nationality": _nationality_field(description),
            "major_scope": _major_scope_field(description),
            "business_registration": _business_registration_field(description),
            "team_policy": _team_policy_field(description),
            "team_size": _team_size_field(description),
        }
        modeled = any(section[key].get("value") is not None for key in section if key != "name")
        section["other_conditions"] = field() if modeled else field([description], description)
        result.append(section)
    return result


def _other_conditions_field(text: str) -> dict:
    patterns = [
        r"(?:관련|해당)\s*전공", r"경력\s*\d+", r"자격증", r"법정대리인.{0,30}(?:동의|서명)",
        r"주최.{0,50}(?:직원|심사위원).{0,30}참가\s*불가", r"참가자\s*1인당.{0,20}(?:작품|출품)",
        r"(?:대회|경진대회).{0,20}참가\s*신청자", r"시상식.{0,15}(?:필수|필참)",
    ]
    found: list[str] = []
    evidence: list[str] = []
    for line in lines(text):
        if any(re.search(pattern, line) for pattern in patterns):
            found.append(re.sub(r"^[-●■※]\s*", "", line).strip())
            evidence.append(line)
    if not found:
        return field()
    return field(found, evidence[0] if len(evidence) == 1 else evidence)


def _breadcrumb_type(html: str) -> tuple[str, str | None] | None:
    matches = re.findall(r'"@id"\s*:\s*"https://linkareer\.com/list/([^"/]+)"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
    mapping = {
        "contest": "공모전", "activity": "대외활동", "activities": "대외활동",
        "intern": "인턴",
        "club": "기타", "education": "기타",
    }
    for slug, name in matches:
        if slug in mapping:
            return mapping[slug], name
        if slug in {"recruit", "job"}:
            title = posting_title(html) or ""
            return ("인턴", title) if re.search(r"인턴(?:십)?", title) else ("기타", name)
    return None


def classify_type(text: str, html: str = "") -> tuple[str, str | None]:
    breadcrumb = _breadcrumb_type(html)
    if breadcrumb:
        return breadcrumb
    patterns = [
        ("인턴", [r"\b인턴(?:십)?\b", r"채용형\s*인턴", r"체험형\s*인턴"]),
        ("공모전", [r"공모전", r"아이디어\s*공모", r"작품\s*공모"]),
        ("대외활동", [r"대외활동", r"서포터즈", r"기자단", r"봉사단", r"홍보대사"]),
    ]
    for posting_type, pats in patterns:
        evidence = first_line(text, pats)
        if evidence:
            return posting_type, evidence
    return "기타", None


def _simple(text: str, pats: list[str]) -> dict:
    evidence = first_line(text, pats)
    return field(labeled_value(evidence), evidence) if evidence else field()


def extract_posting(url: str, html: str, text: str, item_id: str | None = None) -> dict:
    posting_type, type_evidence = classify_type(text, html)
    text = main_posting_text(text)
    data = {"id": item_id, "source_url": url}
    data.update({name: field() for name in COMMON_FIELDS + ALL_TYPE_FIELDS})
    data["type"] = field(posting_type, type_evidence)
    text_lines = lines(text)
    title = posting_title(html)
    if not title:
        title = first_line(text, [r"공모전|대외활동|서포터즈|기자단|봉사단|인턴"])
    if not title and text_lines:
        title = text_lines[0]
    data["title"] = field(title, title) if title else field()
    data["organizer"] = _simple(text, [r"^(주최|주관|기관명|기업명)\s*[:：]"])
    if data["organizer"]["value"] is None:
        data["organizer"] = _header_organizer(text, title)
    deadline_evidence = first_line(text, [r"마감.{0,20}20\d{2}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}", r"(접수|모집|지원).{0,12}20\d{2}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}"])
    if not deadline_evidence:
        deadline_evidence = _direct_deadline_range_evidence(text)
    deadline = _deadline_from_evidence(deadline_evidence or "")
    data["deadline"] = field(deadline.date().isoformat(), deadline_evidence) if deadline and deadline_evidence else field()
    data["region"] = _simple(text, [r"^(지역|활동지역|근무지역)\s*[:：]"])
    if data["region"]["value"] is None:
        data["region"] = _region_field(text)
    data["eligibility"] = _simple(text, [r"^(지원자격|참가자격|모집대상|응모자격)\s*[:：]"])
    if data["eligibility"]["value"] is None:
        data["eligibility"] = _compact_value(text, "참여대상", ["시상규모", "접수기간"])
    both = first_line(text, [r"개인.{0,12}(또는|및|/).{0,12}팀", r"개인\s*/\s*팀", r"혼자도.{0,30}(둘이|팀으로도)"])
    team = first_line(text, [r"팀\s*(참가|지원|단위)", r"\d+\s*인.{0,8}팀"])
    individual = first_line(text, [r"개인.{0,10}(참가|지원|접수)"])
    evidence = both or team or individual
    value = "둘다" if both else "팀" if team else "개인" if individual else None
    data["participation_form"] = field(value, evidence)
    team_evidence = first_line(text, [r"\d+\s*인\s*(이내|이상|이하|~|[-–])?.{0,8}팀", r"팀.{0,12}\d+\s*인", r"둘이\s*한\s*팀"])
    team_match = re.search(r"\d+\s*인(?:\s*(?:이내|이상|이하))?", team_evidence or "")
    if team_match:
        data["team_size"] = field(normalize_space(team_match.group(0)), team_evidence)
    elif team_evidence and re.search(r"둘이\s*한\s*팀", team_evidence):
        data["team_size"] = field("2인", team_evidence)
    onsite_yes = first_line(text, [r"(오프라인|대면|현장).{0,12}(필수|참석|활동|진행)", r"(필수|참석).{0,8}(오프라인|대면|현장)"])
    onsite_no = first_line(text, [r"(온라인|비대면).{0,12}(진행|활동|참여|가능)"])
    data["onsite_required"] = field(True, onsite_yes) if onsite_yes else field(False, onsite_no) if onsite_no else field()
    data["reward"] = _simple(text, [r"상금|시상|혜택"])
    data["period"] = _period_field(text)

    if posting_type == "공모전":
        submission_format = _submission_format_field(text)
        data["deliverable_type"] = dict(submission_format)
        data["submission_format"] = dict(submission_format)
        data["rights_clause"] = _simple(text, [r"저작권|지식재산권|소유권|사용권|귀속"])
        fee = first_line(text, [r"참가비|응모료|출품료"])
        fee_value = "무료" if fee and re.search(r"무료|없음|0\s*원", fee) else labeled_value(fee)
        data["entry_fee"] = field(fee_value, fee) if fee else field()
        data["age"] = _age_field(text)
        data["student_status"] = _student_status_field(text)
        data["region_restriction"] = _region_restriction_field(text)
        data["nationality"] = _nationality_field(text)
        data["major_scope"] = _major_scope_field(text)
        data["business_registration"] = _business_registration_field(text)
        data["team_policy"] = _team_policy_field(text)
        data["team_size"] = _team_size_field(text)
        data["other_conditions"] = _other_conditions_field(text)
        data["sections"] = _section_overrides(text)
    elif posting_type == "대외활동":
        data["activity_period"] = _simple(text, [r"^(활동기간)\s*[:：]"])
        if data["activity_period"]["value"] is None:
            data["activity_period"] = _compact_value(text, "활동기간", ["모집인원", "활동지역"])
        data["weekly_hours"] = _simple(text, [r"주\s*\d+\s*(시간|회)", r"활동시간"])
        data["stipend"] = _simple(text, [r"활동비|지원금|수당"])
    elif posting_type == "인턴":
        data["job_role"] = _simple(text, [r"^(직무|모집부문|담당업무)\s*[:：]"])
        data["employment_type"] = _simple(text, [r"체험형\s*인턴|채용형\s*인턴|계약직|고용형태"])
        data["workplace"] = _simple(text, [r"^(근무지|근무장소|근무지역)\s*[:：]"])
        data["pay"] = _simple(text, [r"급여|월급|연봉|시급"])
    return data


def extract_manifest(manifest: dict, root) -> list[dict]:
    records = []
    for item in manifest["items"]:
        html = (root / item["raw_html_file"]).read_text(encoding="utf-8")
        text = (root / item["raw_text_file"]).read_text(encoding="utf-8")
        record = extract_posting(item["source_url"], html, text, item["id"])
        record["raw_text_file"] = item["raw_text_file"]
        records.append(record)
    return records

