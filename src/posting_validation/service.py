"""Small local web service for the ContestFit prototype.

Network access happens only when a user explicitly previews one official URL.
The service never stores the fetched page, a visitor profile, or an API key.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
import urllib.robotparser
from datetime import UTC, date, datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.parse import parse_qs

from .contest_model import has_conditions, kind_from_title
from .departments import CATALOG, search_catalog, search_schools
from .details import extract_details, scrub
from .extractor import extract_posting
from .parser import html_to_text
from .web_seed import convert_records


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
SEED = WEB / "data" / "seed.json"
CURATED = WEB / "data" / "curated.json"
FEEDBACK = ROOT / "tmp" / "feedback.jsonl"
USER_AGENT = "ContestFit/1.0 (single user-requested official posting preview)"
MAX_BODY = 100_000
MAX_PAGE = 1_000_000
BLOCKED_HOSTS = {
    "linkareer.com", "www.linkareer.com", "thinkyou.co.kr", "www.thinkyou.co.kr",
    "wevity.com", "www.wevity.com", "campuspick.com", "www.campuspick.com",
    "thinkgood.co.kr", "www.thinkgood.co.kr", "all-con.co.kr", "www.all-con.co.kr",
}
_feedback_lock = threading.Lock()
_catalog_lock = threading.Lock()
_catalog_cache: tuple[Path, int, dict] | None = None


class PreviewError(ValueError):
    pass


def validate_url(value: str) -> str:
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise PreviewError("올바른 URL을 입력해 주세요.") from exc
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or port not in (None, 443):
        raise PreviewError("HTTPS 공식 공고 URL만 입력할 수 있습니다.")
    if host in BLOCKED_HOSTS or any(host.endswith("." + name) for name in BLOCKED_HOSTS):
        raise PreviewError("모음 사이트 대신 주최 기관의 공식 공고 URL을 입력해 주세요.")
    if parsed.fragment:
        raise PreviewError("URL의 # 뒤 부분을 지우고 입력해 주세요.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if (address is not None and not address.is_global) or host == "localhost" or host.endswith(".localhost") or "." not in host:
        raise PreviewError("공개된 공식 사이트 주소만 사용할 수 있습니다.")
    return value


def check_public_host(url: str) -> str:
    host = urlsplit(url).hostname or ""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PreviewError("공고 사이트 주소를 확인할 수 없습니다.") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise PreviewError("공개된 공식 사이트 주소만 사용할 수 있습니다.")
    return addresses[0][4][0]


def fetch_limited(url: str, accept: str) -> tuple[bytes, str]:
    address = check_public_host(url)
    parsed = urlsplit(url)
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=12, context=ssl.create_default_context())
    # Pin the checked public address; TLS still verifies the original hostname.
    connection._create_connection = lambda _target, timeout, source_address: socket.create_connection(
        (address, 443), timeout, source_address
    )
    try:
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connection.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept": accept})
        response = connection.getresponse()
        if response.status != 200:
            raise PreviewError("공식 사이트가 자동 열람을 허용하지 않습니다. 원문을 복사해 입력해 주세요.")
        content_type = response.getheader("Content-Type", "").lower()
        data = response.read(MAX_PAGE + 1)
    except (OSError, http.client.HTTPException, TimeoutError) as exc:
        raise PreviewError("공식 사이트를 읽을 수 없습니다. 원문을 복사해 입력해 주세요.") from exc
    finally:
        connection.close()
    if len(data) > MAX_PAGE:
        raise PreviewError("공고 페이지가 너무 큽니다. 원문을 복사해 입력해 주세요.")
    return data, content_type


def fetch_official_html(url: str) -> str:
    parsed = urlsplit(url)
    robots_url = f"https://{parsed.hostname}/robots.txt"
    try:
        robots_bytes, _ = fetch_limited(robots_url, "text/plain")
    except PreviewError as exc:
        raise PreviewError("robots.txt를 확인할 수 없어 자동 열람을 중단했습니다. 원문을 복사해 입력해 주세요.") from exc
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(robots_bytes.decode("utf-8", errors="replace").splitlines())
    if not robots.can_fetch(USER_AGENT, url):
        raise PreviewError("이 사이트의 자동 열람이 허용되지 않습니다. 원문을 복사해 입력해 주세요.")
    time.sleep(max(3.0, robots.crawl_delay(USER_AGENT) or 0))
    page, content_type = fetch_limited(url, "text/html")
    if "text/html" not in content_type:
        raise PreviewError("HTML 공고만 자동 열람할 수 있습니다. PDF 원문은 텍스트를 복사해 입력해 주세요.")
    return page.decode("utf-8", errors="replace")


def preview_contest(source_url: str, pasted_text: str = "") -> dict:
    source_url = validate_url(source_url.strip())
    if len(pasted_text) > 50_000:
        raise PreviewError("붙여넣은 공고 내용이 너무 깁니다.")
    if pasted_text.strip():
        html = ""
        text = pasted_text.strip()
    else:
        html = fetch_official_html(source_url)
        text = html_to_text(html)
    if len(text.strip()) < 30:
        raise PreviewError("자격 조건을 읽을 수 없습니다. 공고 원문을 함께 입력해 주세요.")
    text = scrub(text)
    record = extract_posting(source_url, html, text, "preview", force_type="공모전")
    seed = convert_records([record], datetime.now(UTC).isoformat())
    contest = seed["contests"][0]
    contest["id"] = "official-" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    contest["sections"] = [
        {**section, "id": f"{contest['id']}-section-{index}"}
        for index, section in enumerate(contest["sections"], 1)
    ]
    contest["title"] = contest["title"] or "제목 확인 필요"
    contest["is_sample"] = False
    contest["validation_status"] = "draft"
    contest["deadline"] = record.get("deadline", {}).get("value")
    contest["category"] = None
    contest["topic_tags"] = []
    contest["skill_signals"] = []
    contest["kind"] = kind_from_title(contest["title"], "contest")
    contest["source"] = {"id": "user", "name": "사용자 추가 URL", "type": "user_submission"}
    contest["eligibility_known"] = any(has_conditions(section) for section in contest["sections"])
    contest["details"] = extract_details(text)
    contest["details"]["links"] = [{"label": "원문 공고", "url": source_url}]
    if not contest["deadline"]:
        apply = next((item for item in contest["details"]["schedule"] if item["type"] == "apply"), None)
        contest["deadline"] = (apply or {}).get("end_date") or None
    return contest


def validate_feedback(value: dict) -> dict:
    if not isinstance(value, dict):
        raise PreviewError("피드백 형식이 올바르지 않습니다.")
    if value.get("task_completed") not in (True, False) or value.get("reason_clear") not in (True, False):
        raise PreviewError("과제 완료 여부와 판정 이해 여부를 선택해 주세요.")
    if value.get("ease") not in (1, 2, 3, 4, 5):
        raise PreviewError("사용 편의성을 1~5점으로 선택해 주세요.")
    return {
        "submitted_at": datetime.now(UTC).isoformat(),
        "task_completed": value["task_completed"],
        "reason_clear": value["reason_clear"],
        "ease": value["ease"],
    }


def record_feedback(value: dict) -> None:
    row = validate_feedback(value)
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    with _feedback_lock, FEEDBACK.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_catalog() -> dict:
    """Reuse the parsed catalog until the atomic sync replaces its file."""
    global _catalog_cache
    with _catalog_lock:
        stamp = CATALOG.stat().st_mtime_ns
        if _catalog_cache is None or _catalog_cache[0] != CATALOG or _catalog_cache[1] != stamp:
            _catalog_cache = (CATALOG, stamp, json.loads(CATALOG.read_text(encoding="utf-8")))
        return _catalog_cache[2]


def list_contests(kind: str = "all", deadline: str = "all", query: str = "", limit: int | None = None) -> dict:
    if kind not in ("all", "real", "sample") or deadline not in ("all", "open", "unknown"):
        raise ValueError("공고 조회 조건이 올바르지 않습니다.")
    if limit is not None and not 1 <= limit <= 200:
        raise ValueError("조회 건수는 1~200이어야 합니다.")
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    curated = json.loads(CURATED.read_text(encoding="utf-8")) if CURATED.exists() else {"contests": []}
    contests = curated["contests"] + seed["contests"]
    if kind != "all":
        contests = [item for item in contests if bool(item.get("is_sample")) == (kind == "sample")]
    if deadline != "all":
        today = date.today().isoformat()
        if deadline == "unknown":
            contests = [item for item in contests if not item.get("deadline")]
        else:
            contests = [item for item in contests if item.get("deadline") and item["deadline"] >= today]
    if query:
        needle = query.strip().casefold()
        contests = [item for item in contests if needle in f"{item.get('title') or ''} {item.get('organizer') or ''}".casefold()]
    seed["contests"] = contests[:limit] if limit else contests
    return seed


def data_status() -> dict:
    data = list_contests()
    catalog = load_catalog()
    school_count = catalog.get("school_count")
    if school_count is None:
        school_count = len({item.get("school") for item in catalog.get("departments", []) if item.get("school")})
    return {
        "sample_contests": sum(bool(item.get("is_sample")) for item in data["contests"]),
        "verified_contests": sum(not item.get("is_sample") and item.get("validation_status") == "verified" for item in data["contests"]),
        "departments": len(catalog.get("departments", [])),
        "schools": school_count,
        "reference_year": catalog.get("reference_year"),
        "synced_at": catalog.get("synced_at"),
    }


class Handler(SimpleHTTPRequestHandler):
    # Browsers refuse ES modules served as text/plain. On Windows the registry-based
    # mime table has no .mjs entry, so declare it instead of relying on the OS.
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".mjs": "text/javascript"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def send_json(self, status: HTTPStatus, value: dict) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _api(self, method: str) -> None:
        from . import api  # imported lazily: api depends on this module

        parsed = urlsplit(self.path)
        body = None
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            body = self.rfile.read(length) if 0 < length <= MAX_BODY else b""
        status, payload = api.handle(method, parsed.path, parsed.query, body)
        self.send_json(HTTPStatus(status), payload)

    def do_GET(self) -> None:
        if urlsplit(self.path).path.startswith("/api/"):
            self._api("GET")
        else:
            super().do_GET()

    def do_POST(self) -> None:
        self._api("POST")


def main() -> None:
    parser = argparse.ArgumentParser(description="ContestFit local web service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        print(f"ContestFit: http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
