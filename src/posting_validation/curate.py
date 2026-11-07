"""Review and publish a single official contest preview into curated.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import CURATED, validate_url


CONDITION_FIELDS = (
    "age", "status", "major_scope", "region", "nationality", "business_reg", "entry_type", "team_size"
)


def specified(section: dict, field: str) -> bool:
    value = section.get(field)
    if field == "age":
        return isinstance(value, dict) and (value.get("min") is not None or value.get("max") is not None)
    if field == "status":
        return isinstance(value, dict) and (value.get("allowed") is not None or value.get("excluded") is not None)
    if field == "business_reg":
        return isinstance(value, dict) and (value.get("policy") is not None or value.get("years") is not None)
    if field == "team_size":
        return isinstance(value, dict) and (value.get("min") is not None or value.get("max") is not None)
    return value not in (None, "", "제한없음")


def verify_contest(contest: dict) -> dict:
    if not isinstance(contest, dict) or not contest.get("title") or not contest.get("sections"):
        raise ValueError("공고 제목과 부문별 조건이 필요합니다.")
    validate_url(contest.get("source_url", ""))
    if contest.get("is_sample") is not False:
        raise ValueError("샘플 공고는 실제 공고로 검수할 수 없습니다.")
    if not contest.get("collected_at"):
        raise ValueError("수집 시각이 필요합니다.")
    if any(key in contest for key in ("raw_text", "html", "full_text", "poster")):
        raise ValueError("공고 전문과 이미지는 저장할 수 없습니다.")
    if not isinstance(contest.get("topic_tags", []), list) or not isinstance(contest.get("skill_signals", []), list):
        raise ValueError("주제와 역량 신호는 배열이어야 합니다.")
    for topic in contest.get("topic_tags", []):
        if not isinstance(topic, str) or not topic.strip() or len(topic) > 60:
            raise ValueError("주제 태그를 확인해 주세요.")
    for signal in contest.get("skill_signals", []):
        if not isinstance(signal, dict) or not isinstance(signal.get("name"), str) or not isinstance(signal.get("evidence"), str):
            raise ValueError("역량 신호에는 이름과 원문 근거가 필요합니다.")
        if not signal["name"].strip() or not signal["evidence"].strip() or len(signal["evidence"]) > 300:
            raise ValueError("역량 신호의 짧은 원문 근거를 확인해 주세요.")
    for section in contest["sections"]:
        for field in CONDITION_FIELDS:
            if not specified(section, field):
                continue
            evidence = section.get("evidence", {}).get(field)
            excerpts = evidence if isinstance(evidence, list) else [evidence]
            if not excerpts or any(not isinstance(item, str) or not item.strip() or len(item) > 300 for item in excerpts):
                raise ValueError(f"{field}: 짧은 원문 근거를 확인해 주세요.")
    return {**contest, "validation_status": "verified"}


def publish(contest: dict, output: Path = CURATED) -> None:
    checked = verify_contest(contest)
    data = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"schema_version": "1.1", "contests": []}
    items = [item for item in data["contests"] if item["source_url"] != checked["source_url"]]
    items.append(checked)
    data["contests"] = items
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a manually checked official ContestFit preview")
    parser.add_argument("--input", required=True, type=Path, help="downloaded preview JSON after manual comparison with the original")
    args = parser.parse_args()
    value = json.loads(args.input.read_text(encoding="utf-8"))
    publish(value.get("contest", value))
    print(f"검수된 공고 저장: {CURATED}")


if __name__ == "__main__":
    main()
