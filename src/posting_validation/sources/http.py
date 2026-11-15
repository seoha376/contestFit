"""Small HTTP helpers for official APIs.

Errors never include the request URL, query string or headers because they can
carry API keys. Fixture mode reads recorded payloads so CI and E2E tests run
without network access or secrets.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


USER_AGENT = "ContestFit/2.0 (+https://github.com/seoha376/contestFit; official API client)"
MAX_BYTES = 3_000_000
FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sources"


class SourceError(RuntimeError):
    """A safe-to-display error that never contains secrets."""


def mode() -> str:
    """live (default), fixture (recorded payloads) or off (no external calls)."""
    value = os.environ.get("CONTESTFIT_SOURCE_MODE", "live").strip().lower()
    return value if value in ("live", "fixture", "off") else "live"


_TOKEN = re.compile(r"\{\{D([+-]\d+):(ymd|iso|dot|yy|epoch|isoz)\}\}")


def _render_dates(text: str) -> str:
    """Fixtures use {{D+10:ymd}} tokens so recorded payloads never expire."""
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    def replace(match: re.Match) -> str:
        day = today + timedelta(days=int(match.group(1)))
        style = match.group(2)
        if style == "ymd":
            return day.strftime("%Y%m%d")
        if style == "dot":
            return day.strftime("%Y.%m.%d")
        if style == "yy":
            return day.strftime("%y-%m-%d")
        if style == "epoch":
            return str(int(datetime(day.year, day.month, day.day, 23, 35, tzinfo=ZoneInfo("Asia/Seoul")).timestamp()))
        if style == "isoz":
            return f"{day.isoformat()}T14:59:00Z"
        return day.isoformat()

    return _TOKEN.sub(replace, text)


def fixture(name: str) -> bytes:
    path = FIXTURES / name
    if not path.exists():
        raise SourceError(f"fixture {name} 없음")
    return _render_dates(path.read_text(encoding="utf-8")).encode("utf-8")


def get(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 12,
        source: str = "API") -> bytes:
    query = urllib.parse.urlencode(params or {}, doseq=True, safe="[]:")
    full = f"{url}?{query}" if query else url
    request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise SourceError(f"{source} 응답 HTTP {exc.code}") from None
    except (OSError, ValueError):
        raise SourceError(f"{source} 연결 실패") from None
    if len(data) > MAX_BYTES:
        raise SourceError(f"{source} 응답이 너무 큽니다")
    return data


def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 12,
             source: str = "API"):
    data = get(url, params, {"Accept": "application/json", **(headers or {})}, timeout, source)
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SourceError(f"{source} 응답이 JSON 형식이 아닙니다") from None
