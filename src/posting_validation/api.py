"""Framework-free HTTP API shared by the local server and the WSGI app (Vercel).

``handle(method, path, query, body)`` returns ``(status, payload)``. The browser
never receives API keys: official APIs are called here, normalized into the
contest schema and judged client-side by ``web/decision-engine.mjs``.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import UTC, date, datetime
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs

from . import service, sources
from .contest_model import KIND_LABELS, today_kst
from .departments import search_catalog, search_schools
from .details import merge_details
from .page_extract import analyze_text
from .parser import html_to_text
from .sources import careernet, http as source_http
from .store import StoreError, get_store


ROOT = Path(__file__).resolve().parents[2]
PAGE_FIXTURES = ROOT / "tests" / "fixtures" / "pages"
ANALYSIS_TTL = 24 * 3600
_analyze_lock = threading.Lock()
_last_analyze: dict[str, float] = {}


class ApiError(ValueError):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status


def _int(params: dict, name: str, default: int | None, low: int, high: int) -> int | None:
    if name not in params:
        return default
    try:
        value = int(params[name][0])
    except ValueError:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{name} 값이 올바르지 않습니다.") from None
    if not low <= value <= high:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{name}은(는) {low}~{high} 사이여야 합니다.")
    return value


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"contests": []}


def _with_analysis(contest: dict, store) -> dict:
    cached = store.cache_get(f"analysis:{contest['id']}") if store else None
    return cached or contest


def aggregate(include_samples: bool = True) -> dict:
    store = get_store()
    curated = _read_json(service.CURATED).get("contests", [])
    try:
        submissions = store.list_submissions()
        store_status = {"backend": store.backend, "ok": True}
    except StoreError as exc:
        submissions, store_status = [], {"backend": store.backend, "ok": False, "error": str(exc)}
    live = sources.collect(store)
    analyzed = {key.split(":", 1)[1]: value for key, value in store.cache_prefix("analysis:").items()}
    live_contests = [analyzed.get(contest["id"], contest) for contest in live["contests"]]
    seen: set[str] = set()
    contests: list[dict] = []
    for contest in [*curated, *live_contests, *submissions]:
        key = contest.get("source_url") or contest.get("id")
        if key in seen:
            continue
        seen.add(key)
        contests.append(contest)
    if include_samples:
        contests.extend(_read_json(service.SEED).get("contests", []))
    return {"contests": contests, "sources": live["sources"], "store": store_status}


def list_contests(params: dict) -> dict:
    kind = params.get("kind", ["all"])[0]
    deadline = params.get("deadline", ["all"])[0]
    category = params.get("type", ["all"])[0]
    source = params.get("source", ["all"])[0]
    query = params.get("q", [""])[0][:100].strip().casefold()
    include_samples = params.get("samples", ["1"])[0] != "0"
    limit = _int(params, "limit", None, 1, 500)
    if kind not in ("all", "real", "sample") or deadline not in ("all", "open", "unknown"):
        raise ApiError(HTTPStatus.BAD_REQUEST, "공고 조회 조건이 올바르지 않습니다.")
    if category not in ("all", *KIND_LABELS):
        raise ApiError(HTTPStatus.BAD_REQUEST, "공고 유형이 올바르지 않습니다.")
    data = aggregate(include_samples or kind == "sample")
    contests = data["contests"]
    today = today_kst().isoformat()
    if kind != "all":
        contests = [item for item in contests if bool(item.get("is_sample")) == (kind == "sample")]
    if deadline == "open":
        contests = [item for item in contests if item.get("deadline") and item["deadline"] >= today]
    elif deadline == "unknown":
        contests = [item for item in contests if not item.get("deadline")]
    if category != "all":
        contests = [item for item in contests if (item.get("kind") or "contest") == category]
    if source != "all":
        contests = [item for item in contests if (item.get("source") or {}).get("id", "sample" if item.get("is_sample") else "curated") == source]
    if query:
        contests = [item for item in contests if query in f"{item.get('title') or ''} {item.get('organizer') or ''} {item.get('category') or ''}".casefold()]
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "contests": contests[:limit] if limit else contests,
        "sources": data["sources"],
        "store": data["store"],
    }


def find_contest(contest_id: str) -> dict | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,80}", contest_id):
        raise ApiError(HTTPStatus.BAD_REQUEST, "공고 ID가 올바르지 않습니다.")
    store = get_store()
    for contest in _read_json(service.CURATED).get("contests", []) + _read_json(service.SEED).get("contests", []):
        if contest.get("id") == contest_id:
            return contest
    try:
        for contest in store.list_submissions():
            if contest.get("id") == contest_id:
                return contest
    except StoreError:
        pass
    found = sources.find(contest_id, store)
    return _with_analysis(found, store) if found else None


def _page_text(url: str) -> tuple[str, str]:
    """Fetch one official page (robots-checked) or a recorded page in fixture mode."""
    if source_http.mode() == "fixture":
        index = json.loads((PAGE_FIXTURES / "index.json").read_text(encoding="utf-8"))
        name = index.get(url)
        if not name:
            raise service.PreviewError("테스트 원문이 없습니다. 원문을 붙여넣어 분석해 주세요.")
        html = source_http._render_dates((PAGE_FIXTURES / name).read_text(encoding="utf-8"))
        return html, html_to_text(html)
    if source_http.mode() == "off":
        raise service.PreviewError("외부 열람이 꺼져 있습니다. 원문을 붙여넣어 분석해 주세요.")
    service.validate_url(url)
    html = service.fetch_official_html(url)
    return html, html_to_text(html)


def analyze_contest(contest_id: str, pasted_text: str = "") -> dict:
    """Read the official page behind an API listing and merge eligibility, schedule and deliverables."""
    contest = find_contest(contest_id)
    if not contest:
        raise ApiError(HTTPStatus.NOT_FOUND, "공고를 찾을 수 없습니다.")
    store = get_store()
    if not pasted_text:
        cached = store.cache_get(f"analysis:{contest_id}")
        if cached:
            return cached
    with _analyze_lock:
        if time.time() - _last_analyze.get(contest_id, 0) < 5 and not pasted_text:
            raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "잠시 후 다시 시도해 주세요.")
        _last_analyze[contest_id] = time.time()
    if len(pasted_text) > 50_000:
        raise ApiError(HTTPStatus.BAD_REQUEST, "붙여넣은 원문이 너무 깁니다.")
    if pasted_text.strip():
        html, text = "", pasted_text.strip()
    else:
        html, text = _page_text(contest["source_url"])
    analysis = analyze_text(contest["source_url"], text, html, contest_id)
    updated = dict(contest)
    updated["details"] = merge_details(contest.get("details"), analysis["details"])
    if not contest.get("eligibility_known", True) or not contest.get("source"):
        if analysis["eligibility_found"]:
            updated["sections"] = [{**section, "id": f"{contest_id}-section-{index}"} for index, section in enumerate(analysis["sections"], 1)]
            updated["eligibility_known"] = True
    if not updated.get("deadline") and analysis["deadline"]:
        updated["deadline"] = analysis["deadline"]
    updated["analysis"] = {
        "analyzed_at": datetime.now(UTC).isoformat(),
        "method": "pasted_text" if pasted_text else "official_page",
        "eligibility_found": analysis["eligibility_found"],
        "schedule_items": len(analysis["details"]["schedule"]),
        "deliverables": len(analysis["details"]["deliverables"]),
    }
    store.cache_put(f"analysis:{contest_id}", updated, ANALYSIS_TTL)
    if (contest.get("source") or {}).get("type") == "user_submission":
        store.upsert_submission(updated)
    return updated


def preview(value: dict) -> dict:
    url = service.validate_url(str(value.get("source_url", "")).strip())
    text = str(value.get("text", ""))
    if not text.strip():
        _, text = _page_text(url)
    return service.preview_contest(url, text)


def submit_url(value: dict) -> dict:
    contest = preview(value)
    get_store().upsert_submission(contest)
    return contest


def search_majors(query: str) -> dict:
    query = query.strip()[:40]
    if len(query) < 2:
        return {"majors": [], "source": None}
    if sources.configured(careernet):
        try:
            return {"majors": careernet.search(sources.env(), query), "source": "커리어넷 학과정보 API"}
        except source_http.SourceError as exc:
            fallback_error = str(exc)
        else:
            fallback_error = None
    else:
        fallback_error = None
    catalog = service.load_catalog()
    families: dict[str, str] = {}
    for item in catalog.get("departments", []):
        major = item.get("major") or ""
        if query in major and item.get("family"):
            families.setdefault(major, item["family"])
        if len(families) >= 20:
            break
    return {"majors": [{"major": major, "family": family, "related": []} for major, family in families.items()],
            "source": "전국대학별학과정보 표준데이터", **({"warning": fallback_error} if fallback_error else {})}


def data_status() -> dict:
    status = service.data_status()
    store = get_store()
    status["store"] = store.health()
    status["source_mode"] = source_http.mode()
    status["sources"] = sources.describe()
    return status


def health() -> dict:
    return {"ok": True, "time": datetime.now(UTC).isoformat(), "source_mode": source_http.mode(),
            "store": get_store().health(), "version": os.environ.get("VERCEL_GIT_COMMIT_SHA", "local")[:12]}


def handle(method: str, path: str, query: str, body: bytes | None) -> tuple[int, dict]:
    params = parse_qs(query)
    try:
        if method == "GET":
            if path == "/api/health":
                return HTTPStatus.OK, health()
            if path == "/api/contests":
                return HTTPStatus.OK, list_contests(params)
            match = re.fullmatch(r"/api/contests/([^/]+)", path)
            if match:
                contest = find_contest(match.group(1))
                if not contest:
                    return HTTPStatus.NOT_FOUND, {"error": "공고를 찾을 수 없습니다."}
                return HTTPStatus.OK, {"contest": contest}
            if path == "/api/sources":
                live = sources.collect(get_store())
                described = {item["id"]: item for item in sources.describe()}
                for item in live["sources"]:
                    described.get(item["id"], {}).update(item)
                return HTTPStatus.OK, {"sources": list(described.values()), "mode": source_http.mode()}
            if path == "/api/departments":
                return HTTPStatus.OK, search_catalog(service.load_catalog(), params.get("q", [""])[0][:80])
            if path == "/api/schools":
                return HTTPStatus.OK, search_schools(service.load_catalog(), params.get("q", [""])[0][:80])
            if path == "/api/majors":
                return HTTPStatus.OK, search_majors(params.get("q", [""])[0])
            if path == "/api/data-status":
                return HTTPStatus.OK, data_status()
            if path == "/api/feedback-summary":
                return HTTPStatus.OK, get_store().feedback_summary()
            return HTTPStatus.NOT_FOUND, {"error": "API를 찾을 수 없습니다."}
        if method == "POST":
            if body is None or not 1 <= len(body) <= service.MAX_BODY:
                raise service.PreviewError("요청 크기가 허용 범위를 벗어났습니다.")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise service.PreviewError("요청 형식이 올바르지 않습니다.")
            if path == "/api/preview":
                return HTTPStatus.OK, {"contest": preview(value)}
            if path == "/api/submissions":
                return HTTPStatus.CREATED, {"contest": submit_url(value)}
            match = re.fullmatch(r"/api/contests/([^/]+)/analyze", path)
            if match:
                return HTTPStatus.OK, {"contest": analyze_contest(match.group(1), str(value.get("text", "")))}
            if path == "/api/feedback":
                get_store().record_feedback(service.validate_feedback(value))
                return HTTPStatus.CREATED, {"saved": True}
            return HTTPStatus.NOT_FOUND, {"error": "API를 찾을 수 없습니다."}
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "허용되지 않는 요청입니다."}
    except ApiError as exc:
        return exc.status, {"error": str(exc)}
    except (service.PreviewError, ValueError, json.JSONDecodeError) as exc:
        return HTTPStatus.BAD_REQUEST, {"error": str(exc) or "요청을 처리할 수 없습니다."}
    except StoreError as exc:
        return HTTPStatus.SERVICE_UNAVAILABLE, {"error": f"저장소 오류: {exc}"}
