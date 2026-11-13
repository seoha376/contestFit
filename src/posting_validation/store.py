"""Minimal runtime storage: user-submitted postings, anonymous feedback, API cache.

Reviewed contests stay in ``web/data/curated.json`` (changed through Git review).
Everything else that the running service writes goes through this module:

* ``LocalStore`` keeps files under ``tmp/`` for development and tests.
* ``SupabaseStore`` talks to Supabase's REST API with the service-role key,
  which only the server holds. Tables have row-level security enabled and no
  public policies, so browsers can never read or write them directly.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAX_SUBMISSIONS = 300


class StoreError(RuntimeError):
    pass


class LocalStore:
    backend = "local"

    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory or os.environ.get("CONTESTFIT_DATA_DIR") or ROOT / "tmp")
        self._lock = threading.Lock()

    def _path(self, name: str) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        return self.directory / name

    def _read(self, name: str, default):
        path = self._path(name)
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _write(self, name: str, value) -> None:
        path = self._path(name)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def list_submissions(self) -> list[dict]:
        rows = self._read("submissions.json", [])
        return [row["contest"] for row in sorted(rows, key=lambda row: row["updated_at"], reverse=True)]

    def upsert_submission(self, contest: dict) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            rows = {row["source_url"]: row for row in self._read("submissions.json", [])}
            previous = rows.get(contest["source_url"])
            rows[contest["source_url"]] = {"source_url": contest["source_url"], "contest": contest,
                                          "created_at": previous["created_at"] if previous else now, "updated_at": now}
            ordered = sorted(rows.values(), key=lambda row: row["updated_at"], reverse=True)[:MAX_SUBMISSIONS]
            self._write("submissions.json", ordered)

    def record_feedback(self, row: dict) -> None:
        with self._lock:
            path = self._path("feedback.jsonl")
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def feedback_summary(self) -> dict:
        path = self._path("feedback.jsonl")
        rows = []
        if path.exists():
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return summarize_feedback(rows)

    def cache_get(self, key: str):
        cache = self._read("cache.json", {})
        entry = cache.get(key)
        if not entry or entry["expires_at"] < time.time():
            return None
        return entry["payload"]

    def cache_prefix(self, prefix: str) -> dict:
        now = time.time()
        return {key: entry["payload"] for key, entry in self._read("cache.json", {}).items()
                if key.startswith(prefix) and entry["expires_at"] > now}

    def cache_put(self, key: str, payload, ttl: int) -> None:
        with self._lock:
            cache = {k: v for k, v in self._read("cache.json", {}).items() if v["expires_at"] > time.time()}
            cache[key] = {"payload": payload, "expires_at": time.time() + ttl}
            self._write("cache.json", cache)

    def health(self) -> dict:
        return {"backend": self.backend, "ok": True}


class SupabaseStore:
    backend = "supabase"

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.key = key

    def _request(self, method: str, table: str, query: dict | None = None, body=None, prefer: str | None = None):
        url = self.base + table + ("?" + urllib.parse.urlencode(query) if query else "")
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read(5_000_000)
        except urllib.error.HTTPError as exc:
            raise StoreError(f"Supabase {table} HTTP {exc.code}") from None
        except (OSError, ValueError):
            raise StoreError(f"Supabase {table} 연결 실패") from None
        return json.loads(raw) if raw else None

    def list_submissions(self) -> list[dict]:
        rows = self._request("GET", "submissions", {"select": "contest", "order": "updated_at.desc", "limit": MAX_SUBMISSIONS})
        return [row["contest"] for row in rows or []]

    def upsert_submission(self, contest: dict) -> None:
        now = datetime.now(UTC).isoformat()
        self._request("POST", "submissions", {"on_conflict": "source_url"},
                      [{"source_url": contest["source_url"], "contest": contest, "updated_at": now}],
                      "resolution=merge-duplicates,return=minimal")

    def record_feedback(self, row: dict) -> None:
        self._request("POST", "feedback", body=[row], prefer="return=minimal")

    def feedback_summary(self) -> dict:
        rows = self._request("GET", "feedback", {"select": "task_completed,reason_clear,ease", "limit": 5000})
        return summarize_feedback(rows or [])

    def cache_get(self, key: str):
        now = datetime.now(UTC).isoformat()
        try:
            rows = self._request("GET", "api_cache", {"select": "payload", "key": f"eq.{key}", "expires_at": f"gt.{now}"})
        except StoreError:
            return None
        return rows[0]["payload"] if rows else None

    def cache_prefix(self, prefix: str) -> dict:
        now = datetime.now(UTC).isoformat()
        try:
            rows = self._request("GET", "api_cache", {"select": "key,payload", "key": f"like.{prefix}*",
                                                      "expires_at": f"gt.{now}", "limit": 500})
        except StoreError:
            return {}
        return {row["key"]: row["payload"] for row in rows or []}

    def cache_put(self, key: str, payload, ttl: int) -> None:
        expires = (datetime.now(UTC) + timedelta(seconds=ttl)).isoformat()
        try:
            self._request("POST", "api_cache", {"on_conflict": "key"}, [{"key": key, "payload": payload, "expires_at": expires}],
                          "resolution=merge-duplicates,return=minimal")
        except StoreError:
            pass  # caching is best effort

    def health(self) -> dict:
        try:
            self._request("GET", "feedback", {"select": "id", "limit": 1})
            return {"backend": self.backend, "ok": True}
        except StoreError as exc:
            return {"backend": self.backend, "ok": False, "error": str(exc)}


def summarize_feedback(rows: list[dict]) -> dict:
    count = len(rows)
    if not count:
        return {"responses": 0, "task_completed_rate": None, "reason_clear_rate": None, "ease_average": None}
    return {
        "responses": count,
        "task_completed_rate": round(sum(bool(row.get("task_completed")) for row in rows) / count, 3),
        "reason_clear_rate": round(sum(bool(row.get("reason_clear")) for row in rows) / count, 3),
        "ease_average": round(sum(int(row.get("ease") or 0) for row in rows) / count, 2),
    }


_store = None
_store_lock = threading.Lock()


def get_store():
    global _store
    with _store_lock:
        if _store is None:
            url = os.environ.get("SUPABASE_URL", "").strip()
            key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            _store = SupabaseStore(url, key) if url and key else LocalStore()
        return _store


def reset_store(store=None) -> None:
    global _store
    with _store_lock:
        _store = store
