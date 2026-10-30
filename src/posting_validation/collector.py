from __future__ import annotations

import hashlib
import html as html_lib
import math
import re
import time
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .extractor import classify_domain, classify_type, extract_posting, main_posting_text, posting_title
from .parser import html_to_text, parse_deadline, xml_entries

USER_AGENT = "ContestFitResearchBot/1.0 (local attribute validation; no redistribution)"
SITEMAP_INDEX = "https://linkareer.com/sitemap/sitemapindex.xml"
CONTEST_LIST = "https://linkareer.com/list/contest"


class BudgetExceeded(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect())


def _transport(url: str, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    with _OPENER.open(request, timeout=30) as response:
        return response.read()


class PoliteClient:
    def __init__(
        self,
        user_agent: str = USER_AGENT,
        min_delay: float = 2.0,
        max_requests: int = 150,
        allowed: Callable[[str], bool] | None = None,
        transport: Callable[[str, dict[str, str]], bytes] = _transport,
        clock: object = time,
    ) -> None:
        self.user_agent = user_agent
        self.min_delay = min_delay
        self.max_requests = max_requests
        self.allowed = allowed or (lambda _url: True)
        self.transport = transport
        self.clock = clock
        self.request_count = 0
        self._last_request_at: float | None = None

    def get(self, url: str) -> bytes:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        if self.request_count >= self.max_requests:
            raise BudgetExceeded(f"request budget {self.max_requests} exhausted")
        now = self.clock.monotonic()
        if self._last_request_at is not None:
            wait = self.min_delay - (now - self._last_request_at)
            if wait > 0:
                self.clock.sleep(wait)
        self._last_request_at = self.clock.monotonic()
        self.request_count += 1
        return self.transport(url, {"User-Agent": self.user_agent, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"})


def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _configure_robots(client: PoliteClient) -> str:
    robots_url = "https://linkareer.com/robots.txt"
    robots_text = decode(client.get(robots_url))
    robots = urllib.robotparser.RobotFileParser()
    robots.set_url(robots_url)
    robots.parse(robots_text.splitlines())
    client.allowed = lambda url: robots.can_fetch(client.user_agent, url)
    return robots_url


def is_linkareer_url(url: str, path_prefix: str) -> bool:
    parsed = urlsplit(url)
    try:
        valid_origin = parsed.scheme == "https" and parsed.hostname == "linkareer.com" and parsed.port in (None, 443)
    except ValueError:
        return False
    if not valid_origin or parsed.query or parsed.fragment:
        return False
    patterns = {
        "/activity/": r"/activity/\d+/?",
        "/sitemap/activities/": r"/sitemap/activities/\d+\.xml",
    }
    pattern = patterns.get(path_prefix)
    return bool(pattern and re.fullmatch(pattern, parsed.path))


def select_recent_activity_sitemaps(
    xml_text: str, now: datetime | None = None, limit: int = 4
) -> list[str]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    rows: list[tuple[datetime, str]] = []
    for item in xml_entries(xml_text, "sitemap"):
        loc = item.get("loc", "")
        if not is_linkareer_url(loc, "/sitemap/activities/") or not item.get("lastmod"):
            continue
        try:
            modified = datetime.fromisoformat(item["lastmod"].replace("Z", "+00:00"))
            if modified.tzinfo is None:
                modified = modified.replace(tzinfo=UTC)
        except ValueError:
            continue
        if cutoff <= modified <= now + timedelta(days=1):
            rows.append((modified, loc))
    return [loc for _, loc in sorted(rows, reverse=True)[:limit]]


def urls_from_sitemap(xml_text: str) -> list[str]:
    return [row["loc"] for row in xml_entries(xml_text, "url") if row.get("loc") and is_linkareer_url(row["loc"], "/activity/")]


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def contest_list_url(page: int) -> str:
    if page < 1:
        raise ValueError("page must be positive")
    return f"{CONTEST_LIST}?page={page}"


def contest_urls_from_list_html(document: str) -> list[str]:
    unescaped = html_lib.unescape(document).replace(r"\/", "/")
    found: list[str] = []
    for href in re.findall(r"(?:href|url)\s*[=:]\s*[\"']([^\"']+)[\"']", unescaped, re.I):
        url = urljoin(CONTEST_LIST, href)
        if is_linkareer_url(url, "/activity/") and url not in found:
            found.append(url)
    return found


def is_open_posting(text: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    text = main_posting_text(text)
    deadline = parse_deadline(text, now=now)
    if deadline is not None:
        return deadline.date() >= now.date()
    return bool(re.search(r"상시\s*(모집|채용)|채용\s*시", text))


def collect(output_dir: Path, sitemap_limit: int = 4, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    client = PoliteClient()
    robots_url = _configure_robots(client)
    index_xml = decode(client.get(SITEMAP_INDEX))
    sitemap_urls = select_recent_activity_sitemaps(index_xml, now=now, limit=sitemap_limit)
    candidate_groups: list[list[str]] = []
    for sitemap_url in sitemap_urls:
        if client.request_count >= client.max_requests:
            break
        candidate_groups.append(urls_from_sitemap(decode(client.get(sitemap_url))))
    candidates: list[str] = []
    for index in range(max((len(group) for group in candidate_groups), default=0)):
        for group in candidate_groups:
            if index < len(group):
                candidates.append(group[index])
    candidates = list(dict.fromkeys(candidates))

    targets = {"공모전": 20, "대외활동": 10, "인턴": 10}
    selected: list[dict] = []
    pending: list[tuple[str, str, str, str, str, str]] = []
    pending_counts = {key: 0 for key in targets}
    counts = {key: 0 for key in targets}
    domain_counts = {key: {} for key in targets}

    def persist(url: str, html: str, text: str, posting_type: str, type_evidence: str | None, domain: str) -> None:
        item_id = stable_id(url)
        html_path = raw_dir / f"{item_id}.html"
        text_path = raw_dir / f"{item_id}.txt"
        html_path.write_text(html, encoding="utf-8")
        text_path.write_text(text, encoding="utf-8")
        selected.append({
            "id": item_id, "source_url": url, "type": posting_type,
            "type_evidence": type_evidence, "domain": domain,
            "raw_html_file": str(html_path.relative_to(output_dir)),
            "raw_text_file": str(text_path.relative_to(output_dir)),
        })
        counts[posting_type] += 1
        domain_counts[posting_type][domain] = domain_counts[posting_type].get(domain, 0) + 1

    for url in candidates:
        if client.request_count >= client.max_requests or all(counts[k] + pending_counts[k] >= targets[k] for k in targets):
            break
        try:
            html = decode(client.get(url))
        except (OSError, PermissionError):
            continue
        text = html_to_text(html)
        if not is_open_posting(text, now=now):
            continue
        posting_type, type_evidence = classify_type(text, html)
        if posting_type not in targets or counts[posting_type] + pending_counts[posting_type] >= targets[posting_type]:
            continue
        domain = classify_domain(posting_title(html) or text)
        domain_cap = math.ceil(targets[posting_type] / 2)
        if domain_counts[posting_type].get(domain, 0) < domain_cap:
            persist(url, html, text, posting_type, type_evidence, domain)
        else:
            pending.append((url, html, text, posting_type, type_evidence or "", domain))
            pending_counts[posting_type] += 1
    for url, html, text, posting_type, type_evidence, domain in pending:
        if counts[posting_type] < targets[posting_type]:
            persist(url, html, text, posting_type, type_evidence or None, domain)
    notes = [f"activities 사이트맵에서 {kind} 표본을 목표 {target}건 중 {counts[kind]}건만 찾았습니다." for kind, target in targets.items() if counts[kind] < target]
    manifest = {
        "collected_at": now.isoformat(), "robots_url": robots_url,
        "sitemaps": sitemap_urls, "candidate_count": len(candidates),
        "request_count": client.request_count, "request_limit": client.max_requests,
        "min_delay_seconds": client.min_delay, "targets": targets,
        "counts": counts, "domain_counts": domain_counts, "items": selected,
        "notes": notes,
    }
    return manifest


def collect_contests(
    output_dir: Path,
    existing_manifest: dict,
    target_total: int = 30,
    now: datetime | None = None,
    client: PoliteClient | None = None,
) -> dict:
    now = now or datetime.now(UTC)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    client = client or PoliteClient(max_requests=80)
    if client.max_requests > 80:
        raise ValueError("contest collection request limit must be 80 or less")

    existing = [dict(item) for item in existing_manifest.get("items", []) if item.get("type") == "공모전"]
    selected = list(existing)
    target_new = max(0, target_total - len(existing))
    seen_urls = {item["source_url"] for item in existing}
    list_pages: list[str] = []
    outcomes = {"existing_or_duplicate": 0, "expired": 0, "missing_direct_deadline": 0, "wrong_type": 0, "request_error": 0, "selected": 0}

    robots_url = _configure_robots(client)

    page = 1
    while outcomes["selected"] < target_new and client.request_count < client.max_requests and page <= 20:
        page_url = contest_list_url(page)
        try:
            document = decode(client.get(page_url))
        except (OSError, PermissionError):
            outcomes["request_error"] += 1
            break
        list_pages.append(page_url)
        candidates = contest_urls_from_list_html(document)
        unseen = [url for url in candidates if url not in seen_urls]
        outcomes["existing_or_duplicate"] += len(candidates) - len(unseen)
        if not unseen and page > 1:
            break
        for url in unseen:
            seen_urls.add(url)
            if outcomes["selected"] >= target_new or client.request_count >= client.max_requests:
                break
            try:
                html = decode(client.get(url))
            except (OSError, PermissionError):
                outcomes["request_error"] += 1
                continue
            text = html_to_text(html)
            record = extract_posting(url, html, text)
            if record["type"]["value"] != "공모전":
                outcomes["wrong_type"] += 1
                continue
            deadline_value = record["deadline"]["value"]
            if deadline_value is None:
                outcomes["missing_direct_deadline"] += 1
                continue
            try:
                deadline = datetime.fromisoformat(deadline_value).date()
            except ValueError:
                outcomes["missing_direct_deadline"] += 1
                continue
            if deadline < now.date():
                outcomes["expired"] += 1
                continue
            item_id = stable_id(url)
            html_path = raw_dir / f"{item_id}.html"
            text_path = raw_dir / f"{item_id}.txt"
            html_path.write_text(html, encoding="utf-8")
            text_path.write_text(text, encoding="utf-8")
            selected.append({
                "id": item_id,
                "source_url": url,
                "type": "공모전",
                "type_evidence": record["type"]["evidence"],
                "domain": classify_domain(posting_title(html) or text),
                "raw_html_file": str(html_path.relative_to(output_dir)),
                "raw_text_file": str(text_path.relative_to(output_dir)),
            })
            outcomes["selected"] += 1
        page += 1

    notes = []
    if len(selected) < target_total:
        notes.append(f"공모전 표본을 목표 {target_total}건 중 {len(selected)}건만 확보했습니다.")
    return {
        "collected_at": now.isoformat(),
        "robots_url": robots_url,
        "candidate_source": CONTEST_LIST,
        "list_pages": list_pages,
        "request_count": client.request_count,
        "request_limit": client.max_requests,
        "min_delay_seconds": client.min_delay,
        "target_total": target_total,
        "target_new": target_new,
        "existing_count": len(existing),
        "new_count": outcomes["selected"],
        "counts": {"공모전": len(selected)},
        "candidate_outcomes": outcomes,
        "items": selected,
        "notes": notes,
    }

