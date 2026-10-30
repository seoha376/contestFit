from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from .eligibility import PROFILES, decide_eligibility
from .extractor import COMMON_FIELDS, TYPE_FIELDS, main_posting_text
from .parser import DATE_RE, normalize_space


def evidence_matches(evidence: str | list[str] | None, body: str, normalized_body: str | None = None) -> bool:
    normalized_body = normalized_body if normalized_body is not None else normalize_space(body)
    if isinstance(evidence, list):
        return bool(evidence) and all(normalize_space(item) in normalized_body for item in evidence)
    return evidence is not None and normalize_space(evidence) in normalized_body


def _rule_value(name: str, text: str):
    if name == "deadline":
        for line in text.splitlines():
            if not re.search(r"마감|접수|모집|지원", line):
                continue
            dates = DATE_RE.findall(line)
            if dates:
                year, month, day = dates[-1]
                return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        return None
    if name == "entry_fee":
        match = re.search(r"(?:참가비|응모료|출품료)\s*[:：]?\s*(무료|없음|0\s*원|[\d,]+\s*원)", text)
        if not match:
            return None
        value = normalize_space(match.group(1))
        return "무료" if re.fullmatch(r"무료|없음|0\s*원", value) else value
    if name == "participation_form":
        if re.search(r"개인.{0,15}(또는|및|/).{0,15}팀", text): return "둘다"
        if re.search(r"(?:팀\s*(?:참가|지원|단위)|\d+\s*인.{0,10}팀)", text): return "팀"
        if re.search(r"개인\s*(?:참가|지원|접수)", text): return "개인"
        return None
    if name == "onsite_required":
        if re.search(r"(?:오프라인|대면|현장).{0,15}(?:필수|참석|활동|진행)", text): return True
        if re.search(r"(?:온라인|비대면).{0,15}(?:진행|활동|참여|가능)", text): return False
        return None
    raise KeyError(name)


def evaluate(records: list[dict], root: Path) -> dict:
    evidence_stats = defaultdict(lambda: [0, 0])
    type_evidence = defaultdict(lambda: [0, 0])
    mismatches = defaultdict(list)
    rule_stats = {name: [0, 0] for name in ["deadline", "entry_fee", "participation_form", "onsite_required"]}
    fill_stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for record in records:
        text = (root / record["raw_text_file"]).read_text(encoding="utf-8")
        normalized_text = normalize_space(text)
        rule_text = main_posting_text(text)
        posting_type = record["type"]["value"]
        active_fields = COMMON_FIELDS + TYPE_FIELDS.get(posting_type, [])
        for name in active_fields:
            evidence_stats[name]
        for name in active_fields:
            obj = record.get(name, {"value": None, "evidence": None})
            fill_stats[posting_type][name][1] += 1
            if obj["value"] is None:
                fill_stats[posting_type][name][0] += 1
            if obj["evidence"] is not None:
                evidence_stats[name][1] += 1
                type_evidence[posting_type][1] += 1
                matched = evidence_matches(obj["evidence"], text, normalized_text)
                evidence_stats[name][0] += int(matched)
                type_evidence[posting_type][0] += int(matched)
                if not matched and len(mismatches[name]) < 5:
                    mismatches[name].append({"id": record["id"], "value": obj["value"], "evidence": obj["evidence"], "position": "not found"})
        for name in rule_stats:
            if name not in active_fields:
                continue
            rule = _rule_value(name, rule_text)
            extracted = record[name]["value"]
            if rule is not None or extracted is not None:
                rule_stats[name][1] += 1
                matched = rule == extracted
                rule_stats[name][0] += int(matched)
                if not matched and len(mismatches[name]) < 5:
                    evidence = record[name]["evidence"]
                    position = text.find(evidence[0] if isinstance(evidence, list) and evidence else evidence) if evidence else -1
                    mismatches[name].append({"id": record["id"], "value": extracted, "rule_value": rule, "evidence": evidence, "position": position})
    total_matched = sum(v[0] for v in evidence_stats.values())
    total_checked = sum(v[1] for v in evidence_stats.values())
    def ratio(a, b): return round(a / b, 4) if b else None
    result = {
        "evidence": {
            "overall": {"matched": total_matched, "checked": total_checked, "rate": ratio(total_matched, total_checked)},
            "by_field": {k: {"matched": v[0], "checked": v[1], "rate": ratio(*v)} for k, v in sorted(evidence_stats.items())},
            "by_type": {k: {"matched": v[0], "checked": v[1], "rate": ratio(*v)} for k, v in sorted(type_evidence.items())},
        },
        "rules": {k: {"matched": v[0], "checked": v[1], "match_rate": ratio(*v)} for k, v in rule_stats.items()},
        "fill": {
            "by_type": {typ: {field: {"null": v[0], "total": v[1], "null_rate": ratio(*v), "fill_rate": ratio(v[1]-v[0], v[1])} for field, v in fields.items()} for typ, fields in fill_stats.items()},
            "common_field_count": len(COMMON_FIELDS),
            "type_specific_field_count": {k: len(v) for k, v in TYPE_FIELDS.items()},
            "type_specific_to_common_ratio": {k: round(len(v) / len(COMMON_FIELDS), 4) for k, v in TYPE_FIELDS.items()},
        },
        "mismatches": dict(mismatches),
    }
    contest_records = [record for record in records if record.get("type", {}).get("value") == "공모전"]
    nontrivial_count = 0
    distributions = {profile["name"]: {"지원 가능": 0, "확인 필요": 0, "지원 불가": 0} for profile in PROFILES}
    split_count = 0
    cases: list[dict] = []
    for record in contest_records:
        def value(name: str):
            return record.get(name, {}).get("value")

        nontrivial = (
            value("age") is not None
            or value("student_status") not in (None, "제한없음")
            or value("region_restriction") not in (None, "제한없음")
            or value("business_registration") not in (None, "무관")
            or value("team_policy") in ("개인만", "팀만")
            or bool(value("other_conditions"))
        )
        nontrivial_count += int(nontrivial)
        decisions = [decide_eligibility(record, profile) for profile in PROFILES]
        for decision in decisions:
            distributions[decision["profile"]][decision["result"]] += 1
        split_count += int(len({decision["result"] for decision in decisions}) > 1)
        if len(cases) < 10 and any(decision["result"] != "지원 가능" for decision in decisions):
            cases.append({
                "id": record.get("id"),
                "title": record.get("title", {}).get("value"),
                "decisions": [decision for decision in decisions if decision["result"] != "지원 가능"],
            })
    contest_total = len(contest_records)
    result["eligibility"] = {
        "nontrivial_conditions": {"count": nontrivial_count, "total": contest_total, "rate": ratio(nontrivial_count, contest_total)},
        "profile_distribution": distributions,
        "split_postings": {"count": split_count, "total": contest_total, "rate": ratio(split_count, contest_total)},
        "cases": cases,
    }
    return result


def render_report(metrics: dict, manifest: dict) -> str:
    out = ["# 공고 속성 추출 검증 보고서", "", "## 수집 요약", ""]
    out.append(f"- 총 요청: {manifest['request_count']} / {manifest['request_limit']} (요청 간격 최소 {manifest['min_delay_seconds']}초, 직렬 실행)")
    out.append(f"- 유형별 수집: {manifest['counts']}")
    for note in manifest.get("notes", []): out.append(f"- 참고: {note}")
    out += ["", "## A. 근거 일치율", "", f"전체: {metrics['evidence']['overall']}", "", "### 필드별", ""]
    out += [f"- {name}: {value}" for name, value in metrics["evidence"]["by_field"].items()]
    out += ["", "### 유형별", ""] + [f"- {name}: {value}" for name, value in metrics["evidence"]["by_type"].items()]
    out += ["", "## B. 규칙 기반 대조", ""] + [f"- {name}: {value}" for name, value in metrics["rules"].items()]
    out += ["", "## C. 채움률", "", f"- 공통 필드 수: {metrics['fill']['common_field_count']}", f"- 유형 전용 필드 수/공통 필드 수: {metrics['fill']['type_specific_to_common_ratio']}"]
    for typ, fields in metrics["fill"]["by_type"].items():
        common = [fields[n]["fill_rate"] for n in COMMON_FIELDS if n in fields]
        avg = round(sum(v for v in common if v is not None) / len(common), 4) if common else None
        out += ["", f"### {typ}", "", f"공통 필드 평균 채움률: {avg}"]
        out += [f"- {name}: {value}" for name, value in fields.items()]
    out += ["", "## 불일치 사례 (필드별 최대 5개)", ""]
    if not metrics["mismatches"]:
        out.append("불일치 사례 없음.")
    for name, rows in metrics["mismatches"].items():
        out += ["", f"### {name}", ""]
        out += [f"- 추출값 `{row.get('value')}` / 규칙값 `{row.get('rule_value')}` / 근거 `{row.get('evidence')}` / 본문 위치 `{row.get('position')}` / id `{row.get('id')}`" for row in rows[:5]]
    out += ["", "## 해석상 주의", "", "정답표 없이 수행한 내부 일관성 평가다. 근거 존재, 독립 규칙과의 합치, null 채움 정도를 측정하며 의미적 정답 여부를 보장하지 않는다.", ""]
    return "\n".join(out)


def render_eligibility_report(metrics: dict, manifest: dict) -> str:
    compatible_manifest = dict(manifest)
    compatible_manifest.setdefault("min_delay_seconds", 2.0)
    compatible_manifest.setdefault("notes", [])
    base = render_report(metrics, compatible_manifest)
    base = base.replace("# 공고 속성 추출 검증 보고서", "# 공모전 자격 판정 검증 보고서", 1)
    introduction = "\n\n이 보고서는 정답표 없는 근거 기반 일관성 평가이며, 의미적 정답 여부를 보장하지 않는다."
    eligibility = metrics["eligibility"]
    out = [base + introduction, "", "## D. 비자명 조건 비율", ""]
    out.append(f"- {eligibility['nontrivial_conditions']}")
    out += ["", "## E. 프로필별 판정 분포와 판정 분기", ""]
    for profile, distribution in eligibility["profile_distribution"].items():
        out.append(f"- {profile}: {distribution}")
    out.append(f"- 프로필 간 판정이 갈린 공고: {eligibility['split_postings']}")
    out += ["", "## F. 확인 필요·지원 불가 사례 (최대 10건)", ""]
    if not eligibility["cases"]:
        out.append("해당 사례 없음.")
    for case in eligibility["cases"]:
        out += ["", f"### {case['title']}", ""]
        for decision in case["decisions"]:
            reasons = "; ".join(
                f"{reason['message']} / 근거 `{reason.get('evidence')}`"
                for reason in decision["reasons"]
            )
            out.append(f"- {decision['profile']}: {decision['result']} — {reasons}")
    out.append("")
    return "\n".join(out)

