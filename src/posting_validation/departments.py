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
    if not isinstance(payload, dict):
        raise ValueError("학과 API 응답 형식이 예상과 다릅니다.")
    response = payload.get("response", payload)
    if not isinstance(response, dict) or "body" not in response:
        raise ValueError("학과 API 응답에 body가 없습니다.")
    header = response.get("header", {})
    if str(header.get("resultCode", "00")) not in ("00", "0"):
        raise ValueError(f"학과 API가 오류 코드를 반환했습니다: {header.get('resultCode')}")
    body = response.get("body", {})
    if not isinstance(body, dict):
        raise ValueError("학과 API body 형식이 예상과 다릅니다.")
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        raise ValueError("학과 API 응답 형식이 예상과 다릅니다.")
    return items, int(body.get("totalCount", len(items)))


def _api_fields(row: dict) -> dict[str, object]:
    """Match documented SNAKE_CASE names to the API's camelCase JSON keys."""
    return {str(key).replace("_", "").casefold(): value for key, value in row.items()}


def _api_value(fields: dict[str, object], name: str) -> str:
    return str(fields.get(name.replace("_", "").casefold(), "")).strip()


def normalize_departments(rows: list[dict], year: int) -> list[dict]:
    unique: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        fields = _api_fields(row)
        if _api_value(fields, "YR") != str(year):
            continue
        status = _api_value(fields, "SCSBJT_STTS_NM")
        if any(word in status for word in ("폐지", "폐과", "폐쇄")):
            continue
        school = _api_value(fields, "SCHL_NM")
        major = _api_value(fields, "SCSBJT_NM")
        region = _api_value(fields, "CTPV_NM")
        if not school or not major:
            continue
        item = {
            "school": school,
            "major": major,
            "region": region,
            "family": _api_value(fields, "UNIV_ONESLF_AFIL_NM"),
            "year": year,
        }
        unique[(school, major, region)] = item
    return sorted(unique.values(), key=lambda item: (item["school"], item["major"], item["region"]))


def _fetch_payload(api_key: str, year: int, page: int, size: int = 1000) -> dict:
    query = urllib.parse.urlencode({
        "serviceKey": api_key, "pageNo": page, "numOfRows": size, "type": "json", "YR": year,
    })
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(10_000_000))
    except (OSError, ValueError) as exc:
        # Do not include the request URL: it contains the operator's service key.
        raise RuntimeError(f"학과 API {page}페이지를 가져오지 못했습니다.") from None
    return payload


def fetch_page(api_key: str, year: int, page: int, size: int = 1000) -> tuple[list[dict], int]:
    return response_items(_fetch_payload(api_key, year, page, size))


def sync(api_key: str, year: int, output: Path = CATALOG, max_pages: int = 1000) -> dict:
    if not api_key:
        raise ValueError("DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다.")
    rows: list[dict] = []
    total = None
    received = 0
    last_page = 0
    for page in range(1, max_pages + 1):
        items, total = fetch_page(api_key, year, page)
        last_page = page
        received += len(items)
        rows.extend(item for item in items if _api_value(_api_fields(item), "YR") == str(year))
        if received >= total:
            break
        if not items:
            raise RuntimeError(f"학과 API {page}페이지가 비었습니다. 수신 {received}건 / 전체 {total}건. 기존 카탈로그를 유지합니다.")
    if total is None or total < 1:
        raise RuntimeError(f"학과 API가 전체 건수를 {total}건으로 반환했습니다. --diagnose로 응답을 확인해 주세요. 기존 카탈로그를 유지합니다.")
    if received < total:
        raise RuntimeError(f"학과 목록이 모두 수신되지 않았습니다. {last_page}페이지, 수신 {received}건 / 전체 {total}건. 기존 카탈로그를 유지합니다.")
    departments = normalize_departments(rows, year)
    if not departments:
        raise RuntimeError("해당 연도 학과가 없어 기존 카탈로그를 유지합니다. 공시연도를 확인해 주세요.")
    schools = _unique_schools(departments)
    catalog = {
        "source": "한국대학교육협의회 전국대학별학과정보표준데이터",
        "source_url": SOURCE_URL,
        "reference_year": year,
        "synced_at": datetime.now(UTC).isoformat(),
        "coverage_note": "공식 표준데이터의 해당 연도 항목이며 실제 재학·지원 자격은 공고 원문으로 확인",
        "school_count": len(schools),
        "schools": schools,
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


def _unique_schools(departments: list[dict]) -> list[dict]:
    schools: dict[str, str] = {}
    for item in departments:
        school = str(item.get("school", "")).strip()
        if school:
            schools.setdefault(school, str(item.get("region", "")).strip())
    return [{"name": name, "region": region} for name, region in sorted(schools.items())]


def search_schools(catalog: dict, query: str, limit: int = 10) -> dict:
    query = query.strip().casefold()
    schools = catalog.get("schools")
    if not isinstance(schools, list):
        schools = _unique_schools(catalog.get("departments", []))
    matches = [item for item in schools if query in item["name"].casefold()] if len(query) >= 2 else []
    matches.sort(key=lambda item: (not item["name"].casefold().startswith(query), len(item["name"]), item["name"]))
    return {
        "schools": matches[:limit],
        "count": len(schools),
        "source": catalog.get("source"),
        "reference_year": catalog.get("reference_year"),
        "coverage_note": catalog.get("coverage_note"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official nationwide department names")
    parser.add_argument("--year", type=int, required=True, help="published year confirmed on the official data page")
    parser.add_argument("--diagnose", action="store_true", help="inspect first page counts without writing data or showing the key")
    args = parser.parse_args()
    api_key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "")
    if args.diagnose:
        if not api_key:
            parser.error("DATA_GO_KR_SERVICE_KEY 환경변수가 필요합니다.")
        payload = _fetch_payload(api_key, args.year, 1)
        items, total = response_items(payload)
        years = sorted({_api_value(_api_fields(item), "YR") for item in items if _api_value(_api_fields(item), "YR")})
        print(f"첫 페이지: {len(items)}건 / API 전체: {total}건 / 요청 연도: {args.year}")
        print(f"첫 페이지에 포함된 연도: {', '.join(years) if years else '(없음)'}")
        response = payload.get("response", payload)
        print(f"응답 구조: 최상위={list(payload)} / body={list(response.get('body', {}))}")
        print(f"첫 행의 필드명: {list(items[0]) if items else []}")
        print("진단만 수행했습니다. 카탈로그는 변경하지 않았습니다.")
        return
    result = sync(api_key, args.year)
    print(f"학과 {len(result['departments'])}건을 저장했습니다: {CATALOG}")


if __name__ == "__main__":
    main()
