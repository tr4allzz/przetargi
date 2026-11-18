"""UK Find a Tender (FTS) and Contracts Finder, both publish OCDS JSON.

FTS is SLOW (measured Nov 2026: ~90-180 s per page of 50 from GitHub runners), so it is
not in the default daily source list; run it on demand with a short window.

FTS:  GET https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages
      ?updatedFrom=YYYY-MM-DDTHH:MM:SS&updatedTo=...&limit=100   (cursor in links.next)
CF:   GET https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search
      ?publishedFrom=YYYY-MM-DD&publishedTo=YYYY-MM-DD&size=100  (cursor in links.next)

Neither supports keyword search, so we page through everything published in the
window and filter client-side. Keep the window short for daily runs.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

FTS_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
CF_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
MAX_PAGES = 400


def release_to_tender(rel: dict, source: str, url_base: str) -> Tender:
    tender = rel.get("tender") or {}
    cpv: set[str] = set()
    cls = tender.get("classification") or {}
    if cls.get("id"):
        cpv.add(str(cls["id"]))
    for it in tender.get("items") or []:
        c = (it.get("classification") or {}).get("id")
        if c:
            cpv.add(str(c))
        for ac in it.get("additionalClassifications") or []:
            if ac.get("id"):
                cpv.add(str(ac["id"]))
    winners: list[str] = []
    value = ""
    for aw in rel.get("awards") or []:
        winners += [x.get("name", "") for x in aw.get("suppliers") or [] if x.get("name")]
        v = aw.get("value") or {}
        if v.get("amount") and not value:
            value = f'{v["amount"]} {v.get("currency", "")}'.strip()
    if not value:
        v = tender.get("value") or {}
        if v.get("amount"):
            value = f'{v["amount"]} {v.get("currency", "")}'.strip()
    buyer = (rel.get("buyer") or {}).get("name", "")
    if not buyer:
        for p in rel.get("parties") or []:
            if "buyer" in (p.get("roles") or []):
                buyer = p.get("name", "")
                break
    ocid = rel.get("ocid") or rel.get("id") or ""
    notice_id = rel.get("id") or ocid
    tag = rel.get("tag") or []
    return Tender(
        source=source,
        source_id=str(notice_id),
        title=tender.get("title") or rel.get("title") or "",
        url=f"{url_base}{notice_id}" if url_base else "",
        description=(tender.get("description") or "")[:2000],
        buyer=buyer,
        country="UK",
        published=(rel.get("date") or "")[:10],
        deadline=((tender.get("tenderPeriod") or {}).get("endDate") or "")[:10],
        notice_type=",".join(tag) if isinstance(tag, list) else str(tag),
        cpv=sorted(cpv),
        value=value,
        winners=sorted(set(winners))[:10],
    )


def _iter_pages(s, url: str, params: dict | None, timeout: int | None = None):
    pages = 0
    while url and pages < MAX_PAGES:
        data = get_json(s, url, params=params, **({"timeout": timeout} if timeout else {}))
        params = None  # next links already carry the query
        pages += 1
        releases = data.get("releases")
        if releases is None:  # Contracts Finder wraps in "results"/"releases" packages
            releases = []
            for pkg in data.get("results") or []:
                releases += pkg.get("releases") or []
        yield releases
        url = (data.get("links") or {}).get("next")


def fetch_fts(s, since: date) -> list[Tender]:
    params = {
        "updatedFrom": datetime.combine(since, time.min).strftime("%Y-%m-%dT%H:%M:%S"),
        "updatedTo": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "limit": 50,
    }
    out: dict[str, Tender] = {}
    n = 0
    for releases in _iter_pages(s, FTS_URL, params, timeout=240):
        for rel in releases:
            t = release_to_tender(rel, "fts", "https://www.find-tender.service.gov.uk/Notice/")
            # FTS release ids look like "012345-2026"; keep only the notice part for the URL
            out[t.key] = t
        n += len(releases)
    log.info("fts: %d releases scanned", n)
    return list(out.values())


def fetch_cf(s, since: date) -> list[Tender]:
    params = {
        "publishedFrom": since.isoformat(),
        "publishedTo": date.today().isoformat(),
        "size": 100,
    }
    out: dict[str, Tender] = {}
    n = 0
    for releases in _iter_pages(s, CF_URL, params):
        for rel in releases:
            t = release_to_tender(rel, "contracts_finder", "")
            # CF ocids look like "ocds-b5fd17-<guid>"; the public notice page uses the guid
            guid = (rel.get("ocid") or "").replace("ocds-b5fd17-", "")
            t.url = f"https://www.contractsfinder.service.gov.uk/Notice/{guid}" if guid else ""
            out[t.key] = t
        n += len(releases)
    log.info("contracts_finder: %d releases scanned", n)
    return list(out.values())
