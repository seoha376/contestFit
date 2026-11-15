"""Turn official posting text into engine sections plus schedule details.

Used for URL previews, official API bodies (KOCCA content) and on-demand detail
lookups. Only short evidence excerpts leave this module.
"""

from __future__ import annotations

from .contest_model import has_conditions, now_iso
from .details import extract_details, scrub
from .extractor import extract_posting
from .web_seed import convert_records


def analyze_text(url: str, text: str, html: str = "", contest_id: str = "page") -> dict:
    text = scrub(text)
    record = extract_posting(url, html, text, contest_id, force_type="공모전")
    converted = convert_records([record], now_iso())["contests"][0]
    sections = converted["sections"]
    return {
        "record": record,
        "title": converted["title"],
        "organizer": converted["organizer"],
        "deadline": converted["deadline"],
        "sections": sections,
        "eligibility_found": any(has_conditions(section) for section in sections),
        "details": extract_details(text),
    }
