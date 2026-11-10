"""Import registering information-security contests from the documented K-CTF API.

API items become private candidates, never verified ContestFit postings.
The operator supplies a key in KCTF_API_KEY only for this manual sync command.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .candidates import import_candidates
from .service import PreviewError, validate_url


API_URL = "https://k-ctf.org/api/v1/contests"
KST = ZoneInfo("Asia/Seoul")
USER_AGENT = "ContestFit/1.0 (manual K-CTF candidate sync)"


def _request_json(url: str, api_key: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}", "Accept": "application/json", "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read(1_000_001))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"K-CTF API가 HTTP {exc.code}를 반환했습니다. 키·권한·호출 한도를 확인해 주세요.") from None
    except (OSError, ValueError):
        # Never include the request object, URL query, or authentication header.
        raise RuntimeError("K-CTF API 호출에 실패했습니다. 키·승인 상태와 네트워크를 확인해 주세요.") from None
    if not isinstance(payload, dict):
        raise ValueError("K-CTF API 응답 형식이 올바르지 않습니다.")
    return payload


def _deadline(value: str | None) -> str:
    if not value:
        return ""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=KST)
        return timestamp.astimezone(KST).date().isoformat()
    except ValueError:
        return ""


def normalize_api_item(item: dict, today: date | None = None) -> dict | None:
    today = today or date.today()
    if not isinstance(item, dict) or item.get("registration_status") == "registration_closed":
        return None
    title = str(item.get("name") or "").strip()
    if len(title) < 3:
        return None
    deadline = _deadline(item.get("apply_end_date"))
    if deadline and deadline < today.isoformat():
        return None
    source_url = ""
    for proposed in (item.get("link"), item.get("url")):
        try:
            source_url = validate_url(str(proposed or "").strip())
            break
        except PreviewError:
            continue
    if not source_url:
        return None
    return {
        "source_url": source_url,
        "title": title,
        "organizer": str(item.get("host") or "").strip(),
        "deadline": deadline,
        "category": "정보보안·CTF",
        "source_name": "K-CTF 공식 API",
    }


def fetch_candidates(api_key: str, max_pages: int = 2, today: date | None = None) -> list[dict]:
    if not api_key:
        raise ValueError("KCTF_API_KEY 환경변수가 필요합니다.")
    found: dict[str, dict] = {}
    for page in range(1, max_pages + 1):
        query = urllib.parse.urlencode({"status": "registering", "page": page, "page_size": 50})
        payload = _request_json(f"{API_URL}?{query}", api_key)
        items = payload.get("items")
        if not isinstance(items, list) or not isinstance(payload.get("total"), int):
            raise ValueError("K-CTF API 목록 응답 형식이 예상과 다릅니다.")
        for item in items:
            candidate = normalize_api_item(item, today)
            if candidate:
                found[candidate["source_url"]] = candidate
        if page * 50 >= payload["total"] or not items:
            break
        time.sleep(0.6)
    return list(found.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync registering K-CTF contests as unverified candidates")
    parser.add_argument("--dry-run", action="store_true", help="show count without changing files")
    args = parser.parse_args()
    candidates = fetch_candidates(os.environ.get("KCTF_API_KEY", ""))
    if args.dry_run:
        print(f"K-CTF API 후보 {len(candidates)}건. 저장하지 않았습니다.")
    else:
        result = import_candidates(candidates)
        print(f"K-CTF API 후보 {result['imported']}건 반영, 전체 후보 {result['total']}건")


if __name__ == "__main__":
    main()
