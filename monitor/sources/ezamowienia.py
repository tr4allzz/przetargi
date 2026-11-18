"""Polish e-Zamówienia / Biuletyn Zamówień Publicznych (BZP).

Public board API (no auth):  GET https://ezamowienia.gov.pl/mo-board/api/v1/notice

Behaviour verified with tools/probe_ezamowienia.py (Nov 2026):
- PublicationDateFrom/To are required and work at DAY granularity (time part ignored).
- PageNumber is ignored. Paging works with SearchAfter=<objectId of the last record>;
  results are ordered by publication time.
- OrderObject=<text> filters server-side on the title (substring, e.g. "walidacj").
- Bursts of requests can get HTTP 403 — we sleep between calls and keep partial results.

Strategy:
- full scan (all notices, incl. htmlBody for description matching) for the last
  FULL_SCAN_DAYS days;
- title keyword search (OrderObject) for the whole window — cheap enough for a 1-year backfill.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta

import requests

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
NOTICE_TYPES = ["ContractNotice", "TenderResultNotice"]
PAGE_SIZE = 500
FULL_SCAN_DAYS = 7
SLEEP = 1.0
MAX_CALLS = 400
TAG_RE = re.compile(r"<[^>]+>")

# Title stems for server-side search (OrderObject is a substring match on the title).
TITLE_STEMS = [
    "walidac", "kwalifikac", "GMP", "GAMP", "farmaceut", "aptek", "radiofarm",
    "krwiodaw", "biobank", "LIMS", "monitoringu temperatur", "monitorowania temperatur",
    "pomieszczeń czystych", "clean room", "Aneks 11",
]


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


_MONEY = r"([\d][\d \u00a0]*(?:[,.]\d{1,2})?\s?(?:PLN|EUR|USD|zł))"
_RX = {
    "estimated_value": re.compile(r"Wartość zamówienia(?: \(?ta wartość[^:]*\)?)?:\s*" + _MONEY),
    "award_value": re.compile(r"Wartość umowy(?:/umowy ramowej)?:\s*" + _MONEY),
    "winner_price": re.compile(r"któremu udzielono zamówienia:\s*" + _MONEY),
    "lowest_offer": re.compile(r"z najniższą ceną lub kosztem:\s*" + _MONEY),
    "highest_offer": re.compile(r"z najwyższą ceną lub kosztem:\s*" + _MONEY),
    "offers": re.compile(r"Liczba otrzymanych ofert lub wniosków:\s*(\d+)"),
    "duration": re.compile(r"Okres realizacji zamówienia albo umowy ramowej:\s*(\d+\s*\w+|do \d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}[^\d]{1,8}\d{4}-\d{2}-\d{2})"),
    "contract_date": re.compile(r"Data zawarcia umowy:\s*(\d{4}-\d{2}-\d{2})"),
    "procedure": re.compile(r"Tryb udzielenia zamówienia wraz z podstawą prawną\s*(.{5,160}?)(?:\s+SEKCJA|\s+\d+\.\d+\.?\))"),
    "deposit": re.compile(r"Zamawiający wymaga wadium:\s*(Tak|Nie)"),
    "deposit_info": re.compile(r"Informacje dotyczące wadium:\s*(.{5,200}?)(?:\s+\d+\.\d+\.?\))"),
    "conditions": re.compile(r"(?:Warunki udziału w postępowaniu|Nazwa i opis warunków udziału w postępowaniu\.?)\s*:?\s*(.{20,700}?)(?:\s+\d+\.\d+\.?\)|\s+SEKCJA)"),
    "framework": re.compile(r"(?:Ogłoszenie dotyczy|zawarcie) umowy ramowej:\s*(Tak|Nie)"),
}
_CRIT = re.compile(r"Nazwa kryterium:\s*(.{2,120}?)\s*\d+\.\d+\.\d+\.?\)\s*Waga:\s*([\d,\.]+)")


def _norm_money(v: str) -> str:
    v = v.replace("\u00a0", " ").replace("zł", "PLN").strip()
    m = re.match(r"([\d ]+)(?:[,.](\d{1,2}))?\s?([A-Z]{3})", v)
    if not m:
        return v
    whole = int(m.group(1).replace(" ", ""))
    return f"{whole:,}".replace(",", " ") + f" {m.group(3)}"


def parse_details(text: str) -> dict:
    """Extract bid-intelligence fields from the plain text of a BZP notice."""
    out: dict = {}
    for k, rx in _RX.items():
        hits = [h.strip() for h in rx.findall(text)]
        if not hits:
            continue
        if k in ("estimated_value", "award_value", "winner_price", "lowest_offer", "highest_offer"):
            hits = list(dict.fromkeys(_norm_money(h) for h in hits))
            out[k] = " / ".join(hits[:5])
        elif k == "offers":
            out[k] = " / ".join(hits[:5])
        else:
            out[k] = hits[0]
    crit = [f"{n.strip()} {w.rstrip('.,')}" for n, w in _CRIT.findall(text)]
    if crit:
        out["criteria"] = list(dict.fromkeys(crit))[:8]
    if not out.get("award_value") and out.get("winner_price"):
        out["award_value"] = out["winner_price"]
    out.pop("winner_price", None)
    dep = out.pop("deposit_info", "")
    if out.get("deposit") == "Tak" and dep:
        out["deposit"] = f"Tak — {dep}"
    if "framework" in out:
        out["framework"] = out["framework"].lower()
    return out


def to_tender(n: dict) -> Tender:
    number = str(_first(n, "bzpNumber", "noticeNumber", "objectId", "id"))
    html = _first(n, "htmlBody", "body", default="")
    desc = TAG_RE.sub(" ", html) if isinstance(html, str) else ""
    desc = " ".join(desc.split())
    details = parse_details(desc)
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
        description=desc[:3000],
        buyer=str(_first(n, "organizationName", "buyerName", "ordererName")),
        country="PL",
        published=str(_first(n, "publicationDate", "publishedDate"))[:10],
        deadline=str(_first(n, "submittingOffersDate", "offersDeadline", "tenderDeadline"))[:16],
        notice_type=str(_first(n, "noticeType", "type")),
        cpv=sorted(set(cpv)),
        winners=_winners(n.get("contractors")),
        tender_id=str(n.get("tenderId") or ""),
        procedure=details.get("procedure", ""),
        estimated_value=details.get("estimated_value", ""),
        award_value=details.get("award_value", ""),
        lowest_offer=details.get("lowest_offer", ""),
        highest_offer=details.get("highest_offer", ""),
        offers=details.get("offers", ""),
        criteria=details.get("criteria", []),
        duration=details.get("duration", ""),
        contract_date=details.get("contract_date", ""),
        framework=details.get("framework", ""),
        deposit=details.get("deposit", ""),
        conditions=details.get("conditions", "")[:600],
    )


class _Client:
    def __init__(self, s):
        self.s = s
        self.calls = 0
        self.logged_keys = False

    def page(self, params: dict) -> list[dict]:
        if self.calls >= MAX_CALLS:
            raise _Blocked(f"call budget {MAX_CALLS} exhausted")
        self.calls += 1
        time.sleep(SLEEP)
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

    def all_pages(self, base: dict, out: dict) -> int:
        """Follow the SearchAfter cursor until a short page. Returns records seen."""
        params, seen, cursor = dict(base, PageSize=PAGE_SIZE), 0, None
        while True:
            if cursor:
                params["SearchAfter"] = cursor
            items = self.page(params)
            seen += len(items)
            for n in items:
                t = to_tender(n)
                if t.source_id:
                    out[t.key] = t
            if len(items) < PAGE_SIZE:
                return seen
            new_cursor = items[-1].get("objectId")
            if not new_cursor or new_cursor == cursor:
                log.warning("ezamowienia: cursor did not advance, stopping")
                return seen
            cursor = new_cursor


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    c = _Client(s)
    today = date.today()
    try:
        # 1) full scan of the recent days (catches matches in the description too)
        full_from = max(since, today - timedelta(days=FULL_SCAN_DAYS))
        for nt in NOTICE_TYPES:
            n = c.all_pages({"NoticeType": nt, "PublicationDateFrom": full_from.isoformat(),
                             "PublicationDateTo": today.isoformat()}, out)
            log.info("ezamowienia full scan %s %s..%s: %d records", nt, full_from, today, n)
        # 2) title keyword search over the whole window
        for nt in NOTICE_TYPES:
            for stem in TITLE_STEMS:
                n = c.all_pages({"NoticeType": nt, "PublicationDateFrom": since.isoformat(),
                                 "PublicationDateTo": today.isoformat(), "OrderObject": stem}, out)
                log.info("ezamowienia title %r %s: %d", stem, nt, n)
    except _Blocked as e:
        log.warning("ezamowienia stopped early (%s); keeping %d records", e, len(out))
    log.info("ezamowienia: %d API calls, %d unique records", c.calls, len(out))
    return list(out.values())
