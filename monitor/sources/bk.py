"""Baza Konkurencyjności (BK2021) — EU-funded procurement in Poland (often private firms).

Search API used by the site's own UI (verified with tools/probe_bk_fts.py, Nov 2026):
  GET /api/announcements/search?page=1&limit=N&sort=default&query=<text>&status[0]=PUBLISHED
  -> {"status": "OK", "data": {"advertisements": [...], "meta": {"total": N}}}
Item keys: id, title (str or [str] with <mark> highlights), content, advertiser_name,
publication_date, submission_deadline, fulfillment_place.
`status[0]` is required (PUBLISHED / CLOSED / RESOLVED); page is 1-based.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

BASE = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl"
SEARCH = f"{BASE}/api/announcements/search"
PAGE_SIZE = 50
MAX_PAGES_PER_QUERY = 10
SLEEP = 1.0
HISTORY_THRESHOLD_DAYS = 30   # include CLOSED/RESOLVED when looking further back than this

QUERIES = ["walidacja", "walidacji", "GMP", "GAMP", "Aneks 11", "kwalifikacja instalacyjna",
           "IQ OQ", "LIMS", "farmaceutyczn"]
TAG_RE = re.compile(r"<[^>]+>")


def _text(v) -> str:
    if isinstance(v, list):
        v = " ".join(str(x) for x in v)
    return " ".join(TAG_RE.sub("", str(v or "")).split())


def to_tender(a: dict) -> Tender:
    aid = str(a.get("id") or "")
    return Tender(
        source="bk",
        source_id=aid,
        title=_text(a.get("title")),
        url=f"{BASE}/ogloszenia/{aid}" if aid else "",
        description=_text(a.get("content"))[:3000],
        buyer=_text(a.get("advertiser_name")),
        country="PL",
        published=str(a.get("publication_date") or "")[:10],
        deadline=str(a.get("submission_deadline") or "")[:16],
        notice_type="zapytanie ofertowe",
    )


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    statuses = ["PUBLISHED"]
    if (date.today() - since).days > HISTORY_THRESHOLD_DAYS:
        statuses += ["CLOSED", "RESOLVED"]
    calls = 0
    for status in statuses:
        for q in QUERIES:
            for page in range(1, MAX_PAGES_PER_QUERY + 1):
                time.sleep(SLEEP)
                calls += 1
                data = get_json(s, SEARCH, params={"page": page, "limit": PAGE_SIZE, "sort": "default",
                                                   "query": q, "status[0]": status})
                items = ((data.get("data") or {}).get("advertisements")) or []
                fresh = 0
                for a in items:
                    t = to_tender(a)
                    if t.source_id and (not t.published or t.published >= since.isoformat()):
                        out[t.key] = t
                        fresh += 1
                if len(items) < PAGE_SIZE or fresh == 0:
                    break
            log.info("bk %s %r: %d unique so far", status, q, len(out))
    log.info("bk: %d API calls, %d records in window", calls, len(out))
    return list(out.values())
