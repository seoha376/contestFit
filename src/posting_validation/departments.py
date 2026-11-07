"""Normalize the official nationwide university department standard API.

The optional sync command needs a key supplied by the operator at runtime.
It is never used during ordinary web requests or tests.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "web" / "data" / "departments.json"
API_URL = "https://api.data.go.kr/openapi/tn_pubr_public_univ_major_api"
SOURCE_URL = "https://www.data.go.kr/data/15107737/standard.do"


def response_items(payload: dict) -> tuple[list[dict], int]:
    response = payload.get("response", {})
    header = response.get("header", {})
    if str(header.get("resultCode", "00")) not in ("00", "0"):
        raise ValueError("학과 API가 오류를 반환했습니다.")
    body = response.get("body", {})
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise ValueError("학과 API 응답 형식이 예상과 다릅니다.")
    return items, int(body.get("totalCount", len(items)))


def normalize_departments(rows: list[dict], year: int) -> list[dict]:
    unique: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        if str(row.get("YR", "")) != str(year):
            continue
        status = str(row.get("SCSBJT_STTS_NM", "")).strip()
        if any(word in status for word in ("폐지", "폐과", "폐쇄")):
            continue
        school = str(row.get("SCHL_NM", "")).strip()
        major = str(row.get("SCSBJT_NM", "")).strip()
        region = str(row.get("CTPV_NM", "")).strip()
        if not school or not major:
            continue
        item = {
            "school": school,
            "major": major,
            "region": region,
            "family": str(row.get("UNIV_ONESLF_AFIL_NM", "")).strip(),
            "year": year,
        }
        unique[(school, major, region)] = item
    return sorted(unique.values(), key=lambda item: (item["school"], item["major"], item["region"]))


def fetch_page(api_key: str, year: int, page: int, size: int = 1000) -> tuple[list[dict], int]:
    query = urllib.parse.urlencode({
        "serviceKey": api_key, "pageNo": page, "numOfRows": size, "type": "json", "YR": year,
    })
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(2_000_000))
    except (OSError, ValueError) as exc:
        # Do not include the request URL: it contains the operator's service key.
        raise RuntimeError(f"학과 API {page}페이지를 가져오지 못했습니다.") from None
    return response_items(payload)


def sync(api_key: str, year: int, output: Path = CATALOG, max_pages: int = 100) -> dict:
    if not api_key:
        raise ValueError("DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다.")
    rows: list[dict] = []
    total = None
    for page in range(1, max_pages + 1):
        items, total = fetch_page(api_key, year, page)
        rows.extend(items)
        if len(rows) >= total:
            break
        if not items:
            raise RuntimeError("학과 API 페이지가 예상보다 일찍 비었습니다.")
    if total is None or len(rows) < total:
        raise RuntimeError("학과 목록이 모두 수신되지 않아 기존 카탈로그를 유지합니다.")
    departments = normalize_departments(rows, year)
    catalog = {
        "source": "한국대학교육협의회 전국대학별학과정보표준데이터",
        "source_url": SOURCE_URL,
        "reference_year": year,
        "synced_at": datetime.now(UTC).isoformat(),
        "coverage_note": "공식 표준데이터의 해당 연도 항목이며 실제 재학·지원 자격은 공고 원문으로 확인",
        "departments": departments,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return catalog


def search_catalog(catalog: dict, query: str, limit: int = 12) -> dict:
    query = query.strip().casefold()
    results = []
    if len(query) >= 2:
        results = [item for item in catalog.get("departments", []) if query in item["major"].casefold() or query in item["school"].casefold()][:limit]
    return {
        "departments": results,
        "count": len(catalog.get("departments", [])),
        "source": catalog.get("source"),
        "reference_year": catalog.get("reference_year"),
        "coverage_note": catalog.get("coverage_note"),
    }


def search_schools(catalog: dict, query: str, limit: int = 10) -> dict:
    query = query.strip().casefold()
    schools: dict[str, str] = {}
    for item in catalog.get("departments", []):
        school = str(item.get("school", "")).strip()
        if school and (not query or query in school.casefold()):
            schools.setdefault(school, str(item.get("region", "")).strip())
    matches = sorted(schools.items(), key=lambda item: (not item[0].casefold().startswith(query), len(item[0]), item[0])) if len(query) >= 2 else []
    return {
        "schools": [{"name": name, "region": region} for name, region in matches[:limit]],
        "count": len({str(item.get("school", "")).strip() for item in catalog.get("departments", []) if item.get("school")}),
        "source": catalog.get("source"),
        "reference_year": catalog.get("reference_year"),
        "coverage_note": catalog.get("coverage_note"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official nationwide department names")
    parser.add_argument("--year", type=int, required=True, help="published year confirmed on the official data page")
    args = parser.parse_args()
    result = sync(os.environ.get("DATA_GO_KR_SERVICE_KEY", ""), args.year)
    print(f"학과 {len(result['departments'])}건을 저장했습니다: {CATALOG}")


if __name__ == "__main__":
    main()
