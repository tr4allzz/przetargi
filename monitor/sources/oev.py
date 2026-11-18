"""Germany — Bekanntmachungsservice (oeffentlichevergabe.de), national notice service.

Covers federal, state and municipal notices INCLUDING below-EU-threshold ones (not in TED).
Open data, CC0, no key (verified with tools/probe_more.py, Nov 2026):
  GET https://oeffentlichevergabe.de/api/notice-exports?pubDay=YYYY-MM-DD&format=ocds.zip
  GET https://oeffentlichevergabe.de/api/notice-exports?pubMonth=YYYY-MM&format=ocds.zip
  -> ZIP of <noticeId>-<version>.json files, each an OCDS release package.
No server-side keyword search: we download the window and filter locally.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import date, timedelta

from ..models import Tender
from .ocds import release_to_tender

log = logging.getLogger(__name__)

URL = "https://oeffentlichevergabe.de/api/notice-exports"
DAILY_LIMIT_DAYS = 31     # longer windows are fetched month by month
TIMEOUT = 300


def _periods(since: date, today: date) -> list[dict]:
    if (today - since).days <= DAILY_LIMIT_DAYS:
        return [{"pubDay": (since + timedelta(days=i)).isoformat()}
                for i in range((today - since).days + 1)]
    out, y, m = [], since.year, since.month
    while (y, m) <= (today.year, today.month):
        out.append({"pubMonth": f"{y:04d}-{m:02d}"})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def to_tender(rel: dict, notice_id: str, version: str) -> Tender:
    t = release_to_tender(rel, "oev", "")
    tender = rel.get("tender") or {}
    t.source_id = f"{notice_id}-{version}" if version else notice_id
    t.url = (f"https://oeffentlichevergabe.de/ui/de/search/details?noticeId={notice_id}"
             f"&noticeVersion={version or '01'}")
    t.country = "DEU"
    t.tender_id = f"oev:{tender.get('id') or rel.get('ocid') or notice_id}"
    t.procedure = tender.get("procurementMethodDetails") or tender.get("procurementMethod") or ""
    is_award = "award" in (rel.get("tag") or []) or bool(rel.get("awards"))
    if is_award and tender.get("numberOfTenderers"):
        t.offers = str(tender["numberOfTenderers"])
    amounts = [(c.get("value") or {}) for c in rel.get("contracts") or []]
    total = sum(a.get("amount") or 0 for a in amounts)
    cur = next((a.get("currency") for a in amounts if a.get("currency")), "EUR")
    if total:
        t.award_value = f"{total:,.0f}".replace(",", " ") + f" {cur}"
        t.contract_date = next(((c.get("dateSigned") or "")[:10] for c in rel.get("contracts") or []
                                if c.get("dateSigned")), "")
    est = (tender.get("value") or {})
    if est.get("amount"):
        t.estimated_value = f"{est['amount']:,.0f}".replace(",", " ") + f" {est.get('currency', 'EUR')}"
    if not t.winners:
        t.winners = sorted({x.get("name", "") for x in tender.get("tenderers") or [] if x.get("name")})[:10] \
            if "award" in (rel.get("tag") or []) else []
    lot_text = " ".join(f"{l.get('title', '')} {l.get('description', '')}" for l in tender.get("lots") or [])
    if lot_text and lot_text not in t.description:
        t.description = (t.description + " " + lot_text)[:3000]
    return t


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    today = date.today()
    files = 0
    for params in _periods(since, today):
        try:
            r = s.get(URL, params={**params, "format": "ocds.zip"}, timeout=TIMEOUT)
            if r.status_code == 404:
                continue          # no export (yet) for this period
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001 — one missing day must not kill the source
            log.warning("oev %s failed: %s", params, e)
            continue
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            files += 1
            stem = name.rsplit("/", 1)[-1][:-5]
            notice_id, _, version = stem.rpartition("-")
            if not notice_id:
                notice_id, version = stem, ""
            try:
                pkg = json.loads(z.read(name))
            except ValueError:
                continue
            for rel in pkg.get("releases") or []:
                t = to_tender(rel, notice_id, version)
                out[t.key] = t
        log.info("oev %s: %d notices so far", params, len(out))
    log.info("oev: %d files, %d notices", files, len(out))
    return list(out.values())
