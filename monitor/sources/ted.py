"""TED (Tenders Electronic Daily) via the official Search API v3.

Docs: https://docs.ted.europa.eu/api/latest/search.html
Anonymous access, POST https://api.ted.europa.eu/v3/notices/search
Expert query syntax, e.g.:  FT~"GAMP" AND publication-date>=20261101
"""
from __future__ import annotations

import logging
from datetime import date

from ..config import QUERY_TERMS
from ..http import post_json
from ..models import Tender

log = logging.getLogger(__name__)

URL = "https://api.ted.europa.eu/v3/notices/search"
FIELDS = [
    "publication-number",
    "notice-title",
    "buyer-name",
    "buyer-country",
    "publication-date",
    "deadline-receipt-tender-date-lot",
    "classification-cpv",
    "notice-type",
    "description-lot",
    "winner-name",
    "links",
]
LANG_PREF = ["eng", "pol", "deu", "ENG", "POL", "DEU"]
PAGE_LIMIT = 100
MAX_PAGES_PER_QUERY = 20


def _pick(v) -> str:
    """TED returns multilingual dicts ({"eng": "...", "pol": [...]}) or lists."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "; ".join(dict.fromkeys(_pick(x) for x in v if _pick(x)))
    if isinstance(v, dict):
        for k in LANG_PREF:
            if k in v and v[k]:
                return _pick(v[k])
        for val in v.values():
            if val:
                return _pick(val)
    return str(v)


def _list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        out: list[str] = []
        for x in v:
            out.extend(_list(x))
        return out
    if isinstance(v, dict):
        out = []
        for x in v.values():
            out.extend(_list(x))
        return out
    return [str(v)]


def _url(n: dict) -> str:
    links = n.get("links") or {}
    html = links.get("html") or {}
    for k in ("ENG", "POL", "DEU"):
        if html.get(k):
            return html[k]
    if html:
        return next(iter(html.values()))
    pn = n.get("publication-number", "")
    return f"https://ted.europa.eu/en/notice/-/detail/{pn}" if pn else ""


def _iso(d: str) -> str:
    # TED returns e.g. "2026-11-13+01:00" or "2026-11-13Z"
    return (d or "")[:10]


def to_tender(n: dict) -> Tender:
    pn = n.get("publication-number") or ""
    deadline = _list(n.get("deadline-receipt-tender-date-lot"))
    return Tender(
        source="ted",
        source_id=pn,
        title=_pick(n.get("notice-title")),
        url=_url(n),
        description=_pick(n.get("description-lot"))[:2000],
        buyer=_pick(n.get("buyer-name")),
        country=_pick(n.get("buyer-country")),
        published=_iso(_pick(n.get("publication-date"))),
        deadline=_iso(deadline[0]) if deadline else "",
        notice_type=_pick(n.get("notice-type")),
        cpv=sorted(set(_list(n.get("classification-cpv")))),
        winners=sorted(set(_list(n.get("winner-name"))))[:10],
    )


def build_query(term: str, since: date) -> str:
    return f'FT~"{term}" AND publication-date>={since.strftime("%Y%m%d")}'


def fetch(s, since: date, terms: list[str] | None = None) -> list[Tender]:
    out: dict[str, Tender] = {}
    for term in terms or QUERY_TERMS:
        q = build_query(term, since)
        for page in range(1, MAX_PAGES_PER_QUERY + 1):
            payload = {
                "query": q,
                "fields": FIELDS,
                "page": page,
                "limit": PAGE_LIMIT,
                "scope": "ALL",
                "paginationMode": "PAGE_NUMBER",
            }
            data = post_json(s, URL, payload)
            notices = data.get("notices") or []
            for n in notices:
                t = to_tender(n)
                if t.source_id:
                    out[t.key] = t
            total = data.get("totalNoticeCount") or 0
            log.info("ted %r page %d: %d notices (total %s)", term, page, len(notices), total)
            if len(notices) < PAGE_LIMIT or page * PAGE_LIMIT >= total:
                break
    return list(out.values())
