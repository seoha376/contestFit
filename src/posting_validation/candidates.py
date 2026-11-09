"""Keep a private, metadata-only queue of official contest candidates.

This module never fetches a posting or assigns eligibility. A reviewer passes a
candidate URL to the existing preview and curation flow separately.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from .service import CURATED, ROOT, validate_url


CANDIDATES = ROOT / "data" / "contest_candidates.json"
FIELDS = ("source_url", "title", "organizer", "deadline", "category", "source_name")
QUEUE_FIELDS = (*FIELDS, "deadline_state", "review_status")


def normalize_candidate(value: dict, now: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError("공고 후보는 객체여야 합니다.")
    url = validate_url(str(value.get("source_url", "")).strip())
    title = str(value.get("title", "")).strip()
    if len(title) < 3 or len(title) > 300:
        raise ValueError("공고 후보 제목을 확인해 주세요.")
    deadline = str(value.get("deadline") or "").strip()
    if deadline:
        try:
            date.fromisoformat(deadline)
        except ValueError as exc:
            raise ValueError("마감일은 YYYY-MM-DD 형식이어야 합니다.") from exc
    fields = {key: str(value.get(key) or "").strip() for key in FIELDS}
    if any(len(fields[key]) > 300 for key in ("organizer", "category", "source_name")):
        raise ValueError("공고 후보 메타데이터가 너무 깁니다.")
    return {
        "id": "official-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
        **fields,
        "source_url": url,
        "status": "candidate",
        "discovered_at": now,
        "updated_at": now,
    }


def read_candidates(path: Path = CANDIDATES) -> dict:
    if not path.exists():
        return {"schema_version": "1", "candidates": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("candidates"), list):
        raise ValueError("후보 저장 파일의 형식이 올바르지 않습니다.")
    return data


def import_candidates(records: list[dict], path: Path = CANDIDATES, now: str | None = None) -> dict:
    now = now or datetime.now(UTC).isoformat()
    prepared = [normalize_candidate(row, now) for row in records]
    data = read_candidates(path)
    existing = {item["source_url"]: item for item in data["candidates"]}
    for item in prepared:
        previous = existing.get(item["source_url"])
        if previous:
            item["discovered_at"] = previous["discovered_at"]
        existing[item["source_url"]] = item
    data["candidates"] = sorted(existing.values(), key=lambda item: (item["deadline"] or "9999-12-31", item["title"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {"imported": len(prepared), "total": len(data["candidates"])}


def load_input(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("candidates") if isinstance(data, dict) else data
        if isinstance(rows, list):
            return rows
    raise ValueError("입력 파일은 공고 후보 배열의 JSON 또는 CSV여야 합니다.")


def summarize(data: dict, today: date | None = None) -> dict:
    today = today or date.today()
    rows = data["candidates"]
    return {
        "total": len(rows),
        "open": sum(bool(item["deadline"]) and item["deadline"] >= today.isoformat() for item in rows),
        "expired": sum(bool(item["deadline"]) and item["deadline"] < today.isoformat() for item in rows),
        "undated": sum(not item["deadline"] for item in rows),
        "source_names": sorted({item["source_name"] for item in rows if item["source_name"]}),
    }


def review_queue(data: dict, curated_path: Path = CURATED, today: date | None = None) -> list[dict]:
    """Prepare a metadata-only handoff; never infer that a candidate was reviewed."""
    today = today or date.today()
    curated = json.loads(curated_path.read_text(encoding="utf-8")) if curated_path.exists() else {"contests": []}
    if not isinstance(curated, dict) or not isinstance(curated.get("contests"), list):
        raise ValueError("검수 공고 파일의 형식이 올바르지 않습니다.")
    published_urls = {
        item.get("source_url") for item in curated["contests"]
        if isinstance(item, dict) and item.get("validation_status") == "verified"
    }
    queue = []
    for item in data["candidates"]:
        deadline = item.get("deadline") or ""
        deadline_state = "undated" if not deadline else "expired" if deadline < today.isoformat() else "open"
        queue.append({
            **{field: item.get(field, "") for field in FIELDS},
            "deadline_state": deadline_state,
            "review_status": "published" if item.get("source_url") in published_urls else "pending",
        })
    priority = {"open": 0, "undated": 1, "expired": 2}
    return sorted(queue, key=lambda item: (
        item["review_status"] == "published", priority[item["deadline_state"]],
        item["deadline"] or "9999-12-31", item["title"],
    ))


def export_review_queue(output: Path, data: dict, curated_path: Path = CURATED, today: date | None = None) -> int:
    queue = review_queue(data, curated_path, today)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=QUEUE_FIELDS)
        writer.writeheader()
        writer.writerows(queue)
    temporary.replace(output)
    return len(queue)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage metadata-only official contest candidates")
    subparsers = parser.add_subparsers(dest="command", required=True)
    importer = subparsers.add_parser("import", help="import CSV or JSON without accessing websites")
    importer.add_argument("--input", type=Path, required=True)
    subparsers.add_parser("report", help="show candidate counts")
    queue_parser = subparsers.add_parser("queue", help="export metadata-only reviewer handoff CSV")
    queue_parser.add_argument("--output", type=Path, default=ROOT / "tmp" / "contest_review_queue.csv")
    args = parser.parse_args()
    if args.command == "import":
        print(json.dumps(import_candidates(load_input(args.input)), ensure_ascii=False))
    elif args.command == "queue":
        count = export_review_queue(args.output, read_candidates())
        print(f"검수 인수 목록 {count}건: {args.output}")
    else:
        print(json.dumps(summarize(read_candidates()), ensure_ascii=False))


if __name__ == "__main__":
    main()
