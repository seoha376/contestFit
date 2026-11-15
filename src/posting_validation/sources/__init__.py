"""Registry of live contest sources.

``collect`` calls each configured source, caches the normalized result for a
short time (memory, then the shared store) and reports per-source status so the
UI can show which official APIs answered. A failing source never hides others.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import careernet, codeforces, http, kaggle, kctf, kocca, kstartup, seoul, work24


CONTEST_SOURCES = [kstartup, kocca, seoul, kctf, codeforces, kaggle, work24]
REFERENCE_SOURCES = [careernet]
CACHE_SECONDS = int(os.environ.get("CONTESTFIT_SOURCE_TTL", "1800"))
_memory: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def env() -> dict:
    names = {name for module in CONTEST_SOURCES + REFERENCE_SOURCES for name in module.SOURCE["env"]}
    return {name: os.environ.get(name, "").strip() for name in names}


def configured(module, values: dict | None = None) -> bool:
    values = values if values is not None else env()
    if http.mode() == "fixture":
        return True
    if http.mode() == "off":
        return False
    return all(values.get(name) for name in module.SOURCE["env"])


def describe() -> list[dict]:
    values = env()
    return [{
        "id": module.SOURCE["id"], "name": module.SOURCE["name"], "type": module.SOURCE["type"],
        "description": module.SOURCE["description"], "homepage": module.SOURCE["homepage"],
        "requires_key": bool(module.SOURCE["env"]), "configured": configured(module, values),
    } for module in CONTEST_SOURCES + REFERENCE_SOURCES]


def _fetch_one(module, values: dict, store) -> dict:
    source_id = module.SOURCE["id"]
    key = f"source:{source_id}:{http.mode()}"
    with _lock:
        cached = _memory.get(key)
    if cached and cached[0] > time.time():
        return cached[1]
    if store is not None:
        stored = store.cache_get(key)
        if stored:
            with _lock:
                _memory[key] = (time.time() + 120, stored)
            return stored
    started = time.time()
    try:
        contests = module.fetch(values)
        result = {"id": source_id, "status": "ok", "count": len(contests), "contests": contests,
                  "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_ms": int((time.time() - started) * 1000)}
        ttl = CACHE_SECONDS
    except http.SourceError as exc:
        result = {"id": source_id, "status": "error", "count": 0, "contests": [], "error": str(exc)[:120],
                  "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_ms": int((time.time() - started) * 1000)}
        ttl = 120
    except Exception:  # an adapter bug must not break the whole listing
        result = {"id": source_id, "status": "error", "count": 0, "contests": [], "error": "응답 처리 중 오류",
                  "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "elapsed_ms": int((time.time() - started) * 1000)}
        ttl = 120
    with _lock:
        _memory[key] = (time.time() + ttl, result)
    if store is not None and result["status"] == "ok":
        store.cache_put(key, result, ttl)
    return result


def collect(store=None, only: set[str] | None = None) -> dict:
    values = env()
    modules = [module for module in CONTEST_SOURCES if configured(module, values) and (not only or module.SOURCE["id"] in only)]
    skipped = [{"id": module.SOURCE["id"], "status": "not_configured", "count": 0}
               for module in CONTEST_SOURCES if module not in modules and (not only or module.SOURCE["id"] in only)]
    results = []
    if modules:
        with ThreadPoolExecutor(max_workers=len(modules)) as pool:
            results = list(pool.map(lambda module: _fetch_one(module, values, store), modules))
    contests = [contest for result in results for contest in result["contests"]]
    status = [{key: value for key, value in result.items() if key != "contests"} for result in results] + skipped
    return {"contests": contests, "sources": status}


def find(contest_id: str, store=None) -> dict | None:
    prefix = contest_id.split("-", 1)[0]
    modules = [module for module in CONTEST_SOURCES if module.SOURCE["id"] == prefix]
    if not modules:
        return None
    data = collect(store, {prefix})
    return next((contest for contest in data["contests"] if contest["id"] == contest_id), None)


def clear_cache() -> None:
    with _lock:
        _memory.clear()
