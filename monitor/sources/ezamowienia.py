"""Polish e-Zamówienia / Biuletyn Zamówień Publicznych (BZP).

Public board API (no auth), used by the ezamowienia.gov.pl search UI:
  GET https://ezamowienia.gov.pl/mo-board/api/v1/notice
      ?NoticeType=ContractNotice&PublicationDateFrom=...&PublicationDateTo=...&PageSize=..

Observed behaviour (Nov 2026): PageNumber is ignored — every page returns the same first
PageSize records — and bursts of requests get HTTP 403. So instead of paging we split the
time window recursively until each slice returns fewer than PageSize records, and we sleep
between calls. A 403 stops the source but keeps everything fetched so far.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta

import requests

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
NOTICE_TYPES = ["ContractNotice", "TenderResultNotice"]
PAGE_SIZE = 500
MIN_SLICE = timedelta(minutes=10)
SLEEP = 1.0
MAX_CALLS = 600
TAG_RE = re.compile(r"<[^>]+>")
FMT = "%Y-%m-%dT%H:%M:%S"


class _Blocked(Exception):
    pass


def _first(d: dict, *keys, default=""):
    for k in keys:
        if d.get(k) not in (None, "", []):
            return d[k]
    return default


def _winners(v) -> list[str]:
    out: list[str] = []
    if isinstance(v, list):
        for c in v:
            if isinstance(c, dict):
                name = _first(c, "contractorName", "name", "organizationName")
                if name:
                    out.append(str(name))
            elif c:
                out.append(str(c))
    elif isinstance(v, str) and v:
        out.append(v)
    return sorted(set(out))[:10]


def to_tender(n: dict) -> Tender:
    number = str(_first(n, "bzpNumber", "noticeNumber", "objectId", "id"))
    html = _first(n, "htmlBody", "body", default="")
    desc = TAG_RE.sub(" ", html) if isinstance(html, str) else ""
    cpv_raw = _first(n, "cpvCode", "cpvCodes", "mainCpvCode", default="")
    cpv = re.findall(r"\d{8}", str(cpv_raw))
    object_id = _first(n, "objectId", "id", default="")
    url = (f"https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{object_id}"
           if object_id else "")
    return Tender(
        source="ezamowienia",
        source_id=number,
        title=str(_first(n, "orderObject", "title", "subject", "name")),
        url=url,
        description=" ".join(desc.split())[:3000],
        buyer=str(_first(n, "organizationName", "buyerName", "ordererName")),
        country="PL",
        published=str(_first(n, "publicationDate", "publishedDate"))[:10],
        deadline=str(_first(n, "submittingOffersDate", "offersDeadline", "tenderDeadline"))[:16],
        notice_type=str(_first(n, "noticeType", "type")),
        cpv=sorted(set(cpv)),
        winners=_winners(n.get("contractors")),
    )


class _Fetcher:
    def __init__(self, s):
        self.s = s
        self.calls = 0
        self.logged_keys = False

    def call(self, nt: str, a: datetime, b: datetime) -> list[dict]:
        if self.calls >= MAX_CALLS:
            raise _Blocked(f"call budget {MAX_CALLS} exhausted")
        self.calls += 1
        time.sleep(SLEEP)
        params = {"NoticeType": nt, "PublicationDateFrom": a.strftime(FMT),
                  "PublicationDateTo": b.strftime(FMT), "PageSize": PAGE_SIZE}
        try:
            data = get_json(self.s, URL, params=params)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 429):
                raise _Blocked(f"HTTP {e.response.status_code} after {self.calls} calls") from e
            raise
        items = data if isinstance(data, list) else (data.get("items") or data.get("data") or [])
        if items and not self.logged_keys:
            log.info("ezamowienia record keys: %s", sorted(items[0].keys()))
            self.logged_keys = True
        return items

    def window(self, nt: str, a: datetime, b: datetime, out: dict) -> None:
        items = self.call(nt, a, b)
        if len(items) >= PAGE_SIZE and (b - a) > MIN_SLICE:
            mid = a + (b - a) / 2
            self.window(nt, a, mid, out)
            self.window(nt, mid, b, out)
            return
        if len(items) >= PAGE_SIZE:
            log.warning("ezamowienia %s %s..%s still >= %d records at min slice", nt, a, b, PAGE_SIZE)
        for n in items:
            t = to_tender(n)
            if t.source_id:
                out[t.key] = t


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    f = _Fetcher(s)
    end = datetime.combine(date.today() + timedelta(days=1), datetime.min.time())
    try:
        for nt in NOTICE_TYPES:
            day = datetime.combine(since, datetime.min.time())
            while day < end:
                nxt = min(day + timedelta(days=1), end)
                before = len(out)
                f.window(nt, day, nxt, out)
                log.info("ezamowienia %s %s: +%d", nt, day.date(), len(out) - before)
                day = nxt
    except _Blocked as e:
        log.warning("ezamowienia stopped early (%s); keeping %d records", e, len(out))
    log.info("ezamowienia: %d API calls, %d records", f.calls, len(out))
    return list(out.values())
