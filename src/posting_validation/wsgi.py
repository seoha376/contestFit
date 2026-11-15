"""WSGI application: ``/api/*`` through ``api.handle`` and static files from ``web/``.

Vercel runs it via ``api/index.py`` (static files are also served by Vercel's CDN);
``python -m posting_validation.wsgi`` runs it locally. Standard library only.
"""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from pathlib import Path

from . import api
from .service import MAX_BODY

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
SECURITY_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("X-Frame-Options", "DENY"),
]
mimetypes.add_type("text/javascript", ".mjs")


def _status_line(code: int) -> str:
    return f"{code} {HTTPStatus(code).phrase}"


def _static(path: str):
    relative = "index.html" if path in ("", "/") else path.lstrip("/")
    target = (WEB / relative).resolve()
    if WEB.resolve() not in target.parents and target != WEB.resolve() / "index.html":
        return None
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        return None
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if content_type.startswith("text/") or content_type in ("application/json", "application/javascript"):
        content_type += "; charset=utf-8"
    cache = "no-cache" if target.suffix in (".html", ".mjs", ".css") else "public, max-age=3600"
    return target.read_bytes(), content_type, cache


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/") or "/"
    query = environ.get("QUERY_STRING", "")
    if path.startswith("/api/"):
        body = None
        if method == "POST":
            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
            except ValueError:
                length = 0
            body = environ["wsgi.input"].read(length) if 0 < length <= MAX_BODY else b""
        status, payload = api.handle(method, path, query, body)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        start_response(_status_line(int(status)), [
            ("Content-Type", "application/json; charset=utf-8"), ("Cache-Control", "no-store"),
            ("Content-Length", str(len(data))), *SECURITY_HEADERS,
        ])
        return [data]
    if method not in ("GET", "HEAD"):
        start_response(_status_line(405), [("Content-Type", "text/plain; charset=utf-8"), *SECURITY_HEADERS])
        return [b"Method Not Allowed"]
    found = _static(path)
    if not found:
        start_response(_status_line(404), [("Content-Type", "text/plain; charset=utf-8"), *SECURITY_HEADERS])
        return [b"Not Found"]
    data, content_type, cache = found
    start_response(_status_line(200), [("Content-Type", content_type), ("Cache-Control", cache),
                                      ("Content-Length", str(len(data))), *SECURITY_HEADERS])
    return [] if method == "HEAD" else [data]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    with make_server("127.0.0.1", 8001, app) as server:  # pragma: no cover - manual run
        print("ContestFit WSGI: http://127.0.0.1:8001")
        server.serve_forever()
