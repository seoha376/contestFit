from __future__ import annotations

import html as html_lib
import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser


class _TextParser(HTMLParser):
    BLOCKS = {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr", "section", "article"}
    IGNORED = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.IGNORED:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORED:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if self._ignored_depth:
            return
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()


def html_to_text(document: str) -> str:
    parser = _TextParser()
    parser.feed(document)
    lines: list[str] = []
    seen: set[str] = set()
    for raw in "".join(parser.parts).splitlines():
        line = normalize_space(raw)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)


DATE_RE = re.compile(r"(?<!\d)(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})(?:일)?")


def parse_deadline(text: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(UTC)
    candidates: list[datetime] = []
    for match in DATE_RE.finditer(text):
        try:
            candidates.append(datetime(*map(int, match.groups()), tzinfo=now.tzinfo or UTC))
        except ValueError:
            continue
    deadline_lines = [line for line in text.splitlines() if re.search(r"마감|접수|모집|지원", line)]
    for line in deadline_lines:
        found = DATE_RE.findall(line)
        if found:
            y, m, d = found[-1]
            try:
                return datetime(int(y), int(m), int(d), tzinfo=now.tzinfo or UTC)
            except ValueError:
                pass
    dday = re.search(r"D\s*[-–]\s*(\d{1,3})", text, re.I)
    if dday:
        return now + timedelta(days=int(dday.group(1)))
    return max(candidates) if candidates else None


def xml_entries(xml_text: str, item_tag: str) -> list[dict[str, str]]:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    result: list[dict[str, str]] = []
    for item in root.findall(f".//{{*}}{item_tag}"):
        row: dict[str, str] = {}
        for child in item:
            row[child.tag.rsplit("}", 1)[-1]] = (child.text or "").strip()
        result.append(row)
    return result

