"""Baza Konkurencyjności (BK2021) — EU-funded private/semipublic procurement in Poland.

EXPERIMENTAL: the BK2021 frontend talks to a JSON API whose exact shape is not documented.
We try the search endpoint; if the response is not what we expect, we log the keys and skip,
so the rest of the run is unaffected. Fix the mapping from the Actions log if needed.
"""
from __future__ import annotations

import logging
from datetime import date

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

BASE = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl"
SEARCH = f"{BASE}/api/announcements/search"
PAGE_SIZE = 100
MAX_PAGES = 30


def to_tender(a: dict) -> Tender:
    aid = str(a.get("id") or a.get("announcementId") or "")
    return Tender(
        source="bk",
        source_id=aid,
        title=str(a.get("title") or a.get("name") or ""),
        url=f"{BASE}/ogloszenia/{aid}" if aid else "",
        description=str(a.get("description") or a.get("subject") or "")[:3000],
        buyer=str(a.get("advertiserName") or a.get("ordererName") or a.get("companyName") or ""),
        country="PL",
        published=str(a.get("publicationDate") or a.get("publishedAt") or "")[:10],
        deadline=str(a.get("submissionDeadline") or a.get("offersDeadline") or "")[:16],
        notice_type="zapytanie ofertowe",
        cpv=[str(c) for c in (a.get("cpvCodes") or []) if c],
    )


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    for page in range(0, MAX_PAGES):
        params = {"page": page, "limit": PAGE_SIZE, "publicationDateFrom": since.isoformat()}
        data = get_json(s, SEARCH, params=params)
        items = data if isinstance(data, list) else (
            data.get("data") or data.get("items") or data.get("content") or [])
        if page == 0:
            log.info("bk response keys: %s", sorted(data.keys()) if isinstance(data, dict) else "list")
            if items:
                log.info("bk record keys: %s", sorted(items[0].keys()))
        for a in items:
            t = to_tender(a)
            if t.source_id and (not t.published or t.published >= since.isoformat()):
                out[t.key] = t
        if len(items) < PAGE_SIZE:
            break
    return list(out.values())
