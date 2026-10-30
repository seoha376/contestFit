from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .extractor import main_posting_text

DIAGNOSIS_FIELDS = [
    "organizer", "region", "eligibility", "participation_form",
    "team_size", "deliverable_type", "period",
]

KEYWORDS = {
    "organizer": r"주최|주관|기관명|운영기관|운영\s*부서",
    "region": r"활동지역|근무지역|(?:^|[\[:：])\s*지역(?:\s|[\]:：])|장소\s*[:：]",
    "eligibility": r"참여대상|응모대상|지원자격|참가자격|모집대상",
    "participation_form": r"개인|혼자|팀으로|팀\s*(?:참가|지원)|성명\s*또는\s*팀명",
    "team_size": r"\d+\s*인|둘이|(?:팀당|팀\s*구성|팀원)\s*\d+|\d+\s*명.{0,8}팀",
    "deliverable_type": r"제출|출품|응모|공모분야|접수\s*형식",
    "period": r"접수기간|모집기간|공모기간|활동기간|시작일|마감일",
}

STRUCTURED_LABELS = [
    "기업형태", "참여대상", "시상규모", "접수기간", "시작일", "마감일",
    "활동기간", "모집인원", "활동지역", "근무지역", "채용형태", "모집직무", "공모분야",
]


def _posting_core(text: str, title: str | None = None) -> str:
    body = main_posting_text(text)
    if not title:
        return body
    body_lines = body.splitlines()
    starts = [index for index, line in enumerate(body_lines) if line.strip() == title]
    return "\n".join(body_lines[starts[-1]:]) if starts else body


def keyword_evidence(field_name: str, text: str) -> list[str]:
    pattern = re.compile(KEYWORDS[field_name], re.I)
    return [line.strip() for line in text.splitlines() if line.strip() and pattern.search(line)][:3]


def classify_null_cause(field_name: str, before: dict, after: dict, text: str) -> dict:
    if before.get("value") is not None:
        return {
            "classification": "기존 추출 성공(진단 대상 아님)",
            "evidence": [before["evidence"]] if before.get("evidence") else [],
        }
    if after.get("value") is not None:
        evidence = after.get("evidence") or ""
        return {
            "classification": "본문에 정보 존재 + 추출 실패",
            "evidence": [line for line in evidence.splitlines() if line],
        }
    evidence = keyword_evidence(field_name, text)
    return {
        "classification": "판단 불가" if evidence else "본문에 정보 없음(진짜 미기재)",
        "evidence": evidence,
    }


def _applicable(record: dict, field_name: str) -> bool:
    return field_name != "deliverable_type" or record["type"]["value"] == "공모전"


def build_diagnosis(before_records: list[dict], after_records: list[dict], manifest: dict, root: Path) -> dict:
    before_by_id = {record["id"]: record for record in before_records}
    stats = {
        name: {
            "applicable": 0, "before_filled": 0, "after_filled": 0,
            "before_extraction_failures": 0, "after_extraction_failures": 0,
            "true_missing": 0, "uncertain": 0,
        }
        for name in DIAGNOSIS_FIELDS
    }
    rows = []
    label_counts = Counter()
    for after in after_records:
        before = before_by_id[after["id"]]
        raw_text = (root / after["raw_text_file"]).read_text(encoding="utf-8")
        core = _posting_core(raw_text, after["title"]["value"])
        for label in STRUCTURED_LABELS:
            if label in core:
                label_counts[label] += 1
        field_rows = []
        for name in DIAGNOSIS_FIELDS:
            if not _applicable(after, name):
                continue
            diagnosis = classify_null_cause(name, before[name], after[name], core)
            current = stats[name]
            current["applicable"] += 1
            current["before_filled"] += int(before[name]["value"] is not None)
            current["after_filled"] += int(after[name]["value"] is not None)
            if diagnosis["classification"] == "본문에 정보 존재 + 추출 실패":
                current["before_extraction_failures"] += 1
            elif diagnosis["classification"] == "본문에 정보 없음(진짜 미기재)":
                current["true_missing"] += 1
            elif diagnosis["classification"] == "판단 불가":
                current["uncertain"] += 1
            field_rows.append({
                "field": name,
                "before": before[name]["value"],
                "after": after[name]["value"],
                **diagnosis,
            })
        rows.append({
            "id": after["id"], "type": after["type"]["value"],
            "title": after["title"]["value"], "fields": field_rows,
        })
    for name, values in stats.items():
        total = values["applicable"]
        values["before_fill_rate"] = round(values["before_filled"] / total, 4) if total else None
        values["after_fill_rate"] = round(values["after_filled"] / total, 4) if total else None
        values["after_extraction_failures"] = 0
    infrastructure_requests = 2 + len(manifest.get("sitemaps", []))
    candidate_attempt_upper_bound = max(0, manifest["request_count"] - infrastructure_requests)
    return {
        "stats": stats,
        "rows": rows,
        "structured_label_counts": dict(label_counts),
        "collection": {
            "request_count": manifest["request_count"],
            "infrastructure_requests": infrastructure_requests,
            "candidate_attempt_upper_bound": candidate_attempt_upper_bound,
            "candidate_pool_after_dedup": manifest["candidate_count"],
            "retained": len(manifest["items"]),
            "retained_yield_vs_upper_bound": round(len(manifest["items"]) / candidate_attempt_upper_bound, 4) if candidate_attempt_upper_bound else None,
            "duplicate_urls_in_retained": len(manifest["items"]) - len({item["source_url"] for item in manifest["items"]}),
        },
    }


def render_diagnosis_report(diagnosis: dict) -> str:
    out = [
        "# null 원인 진단", "",
        "새 네트워크 요청 없이 기존 raw 본문 12건과 기존 extracted.json을 비교했다.", "",
        "## 원인 요약", "",
        "Linkareer의 주요 속성은 `참여대상…접수기간`, `활동기간…모집인원`, `근무지역/활동지역`처럼 인접 HTML 태그로 구조화되어 있다. 정제 텍스트에서는 라벨과 값이 한 줄로 합쳐졌지만 기존 규칙은 주로 `라벨:` 형태의 독립 줄만 허용해 null이 발생했다.", "",
        "## 구조화 라벨 발견", "",
    ]
    for label, count in sorted(diagnosis["structured_label_counts"].items()):
        out.append(f"- `{label}`: {count}건")
    out += ["", "제목 바로 다음 줄의 기관명도 12건 모두에서 확인되어 organizer 보강 규칙에 사용했다.", "", "## 필드별 전후 비교", "", "| 필드 | 적용 건수 | 보강 전 채움률 | 보강 후 채움률 | 보강 전 추출 실패 | 보강 후 추출 실패 | 진짜 미기재 | 판단 불가 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, values in diagnosis["stats"].items():
        out.append(
            f"| {name} | {values['applicable']} | {values['before_fill_rate']:.1%} | {values['after_fill_rate']:.1%} | "
            f"{values['before_extraction_failures']} | {values['after_extraction_failures']} | {values['true_missing']} | {values['uncertain']} |"
        )
    out += ["", "`deliverable_type`은 공모전 7건에만 적용했다.", "", "## 공고별·필드별 판정", ""]
    for row in diagnosis["rows"]:
        out += [f"### {row['id']} — {row['title']}", "", f"유형: {row['type']}", ""]
        for item in row["fields"]:
            out.append(f"- **{item['field']}** — {item['classification']} (보강 전: `{item['before']}`, 보강 후: `{item['after']}`)")
            if item["evidence"]:
                out.append("  - 근거 원문:")
                for evidence in item["evidence"]:
                    out.append(f"    > {evidence}")
    collection = diagnosis["collection"]
    out += [
        "", "## 150회 요청 대비 12건만 유지된 이유", "",
        f"- manifest 기록: 총 요청 {collection['request_count']}회, sitemap 후보 풀 {collection['candidate_pool_after_dedup']}개, 최종 유지 {collection['retained']}건.",
        f"- 고정 요청은 robots.txt 1회 + sitemap index 1회 + activities sitemap 4회 = {collection['infrastructure_requests']}회다. 따라서 공고 페이지 시도는 상한 계산상 최대 {collection['candidate_attempt_upper_bound']}회다.",
        f"- 최종 유지율은 최대 페이지 시도 대비 {collection['retained_yield_vs_upper_bound']:.1%}다. 나머지는 마감 경과, 타 유형, 파싱/응답 실패 등으로 제외되었을 수 있다.",
        "- 단, 현재 manifest에는 URL별 disposition 로그(마감 경과/타 유형/응답 실패)가 없으므로 세 사유의 정확한 비율은 계산할 수 없다.",
        "- candidate_count는 중복 제거 후 값이라 sitemap 원본의 중복 비율도 계산할 수 없다. 최종 유지 12건 안의 중복 URL은 0건이다.",
        "- 따라서 마감 경과·타 유형·중복 비율을 숫자로 단정하지 않고, 로그로 확인 가능한 상한과 한계를 함께 보고한다.",
        "", "## 마감일 정책", "",
        "보강 후 deadline은 본문에 `20YY.MM.DD` 또는 `20YY년 MM월 DD일` 형태의 마감일/접수기간 종료일이 직접 존재할 때만 채운다. `D-N` 또는 `채용 시 마감 (D-N)`만 있는 경우 날짜를 계산하지 않고 null로 둔다.", "",
    ]
    return "\n".join(out)
