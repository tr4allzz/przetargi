"""simap.ch — Swiss public procurement platform (most Swiss tenders are only here, not in TED).

Public REST API used by the site itself (verified with tools/probe_simap.py, Nov 2026):
  GET /rest/publications/v2/project/project-search?search=<text>&lang=de&lang=fr&lang=it&lang=en
      -> {"projects": [...], "pagination": {"lastItem": "YYYYMMDD|n", "itemsPerPage": 20}}
      next page: same query + &lastItem=<pagination.lastItem>; results newest first
  GET /rest/publications/v1/project/{projectId}/publication-details/{publicationId}
      -> procurement (description, CPV), dates.offerDeadline, criteria, decision (vendors, prices,
         numberOfSubmissions, awardDecisionDate)
pubType: tender / award / direct_award / revocation / ...
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

SEARCH = "https://www.simap.ch/rest/publications/v2/project/project-search"
DETAIL = "https://www.simap.ch/rest/publications/v1/project/{pid}/publication-details/{pub}"
LANGS = [("lang", x) for x in ("de", "fr", "it", "en")]
SLEEP = 0.6
MAX_PAGES_PER_QUERY = 15
MAX_DETAILS = 400

QUERIES = ["GMP", "GAMP", "GxP", "Validierung", "validation", "Qualifizierung", "qualification",
           "Computersystem", "Annex 11", "Part 11", "LIMS", "Spitalpharmazie", "Apotheke", "pharmacie",
           "Blutspende", "Reinraum"]
PROCESS = {"open": "offen", "selective": "selektiv", "invitation": "Einladung",
           "direct": "freihändig (z wolnej ręki)", "competition": "Wettbewerb"}
TAG = re.compile(r"<[^>]+>")


def _t(v) -> str:
    """Multilingual {'de':..,'fr':..} -> best available string, HTML stripped."""
    if isinstance(v, dict):
        for k in ("de", "en", "fr", "it"):
            if v.get(k):
                v = v[k]
                break
        else:
            v = ""
    return " ".join(TAG.sub(" ", str(v or "")).replace("&nbsp;", " ").split())


def _chf(x: float, cur: str) -> str:
    return f"{x:,.0f}".replace(",", " ") + f" {cur.upper()}"


def to_tender(item: dict, d: dict | None) -> Tender:
    d = d or {}
    proc = d.get("procurement") or {}
    dates = d.get("dates") or {}
    crit = d.get("criteria") or {}
    dec = d.get("decision") or {}
    info = d.get("project-info") or {}
    lot = d.get("lot") or {}

    cpv = []
    if (proc.get("cpvCode") or {}).get("code"):
        cpv.append(str(proc["cpvCode"]["code"]))
    cpv += [str(c.get("code")) for c in proc.get("additionalCpvCodes") or [] if c.get("code")]

    vendors = dec.get("vendors") or []
    winners = [v.get("vendorName", "") for v in vendors if v.get("vendorName")]
    prices = [(v.get("price") or {}) for v in vendors]
    total = sum(p.get("price") or 0 for p in prices)
    cur = next((p.get("currency") for p in prices if p.get("currency")), "chf")
    winner_info = [(v.get("vendorAddress") or {}).get("countryId") or "" for v in vendors]

    criteria = []
    for c in crit.get("awardCriteria") or []:
        name = _t(c.get("title") or c.get("name"))
        w = c.get("weighting") or c.get("weight")
        if name:
            criteria.append(f"{name} {w}" if w not in (None, "") else name)
    if not criteria and _t(crit.get("awardCriteriaNote")):
        criteria = [_t(crit.get("awardCriteriaNote"))[:120]]

    desc = " ".join(x for x in [_t(proc.get("orderDescription")), _t(proc.get("projectOrderDescription")),
                                 _t(lot.get("title"))] if x)
    buyer = _t(item.get("procOfficeName")) or _t((info.get("procOfficeAddress") or {}).get("name"))
    recipient = _t((info.get("procurementRecipientAddress") or {}).get("name"))
    if recipient and recipient != buyer:
        buyer = f"{buyer} / {recipient}"

    return Tender(
        source="simap",
        source_id=item.get("publicationNumber") or item.get("publicationId") or "",
        title=_t(item.get("title")),
        url=f"https://www.simap.ch/de/project-detail/{item.get('id')}" if item.get("id") else "",
        description=desc[:3000],
        buyer=buyer[:200],
        country="CHE",
        published=str(item.get("publicationDate") or "")[:10],
        deadline=str(dates.get("offerDeadline") or "")[:16].replace("T", " "),
        notice_type=item.get("pubType") or "",
        cpv=sorted(set(cpv)),
        winners=winners[:10],
        tender_id=f"simap:{item.get('id')}" if item.get("id") else "",
        procedure=PROCESS.get(item.get("processType") or "", item.get("processType") or ""),
        award_value=_chf(total, cur) if total else "",
        offers=str(dec.get("numberOfSubmissions") or ""),
        criteria=criteria[:8],
        contract_date=str(dec.get("awardDecisionDate") or "")[:10],
        conditions=_t(crit.get("qualificationCriteriaNote"))[:600],
        winner_info=[x for x in winner_info if x][:5],
        framework="tak" if proc.get("frameworkAgreement") in (True, "yes") else "",
    )


def fetch(s, since: date) -> list[Tender]:
    since_s = since.isoformat()
    items: dict[str, dict] = {}
    calls = 0
    for q in QUERIES:
        last = None
        for _ in range(MAX_PAGES_PER_QUERY):
            params = [("search", q), *LANGS] + ([("lastItem", last)] if last else [])
            time.sleep(SLEEP)
            calls += 1
            data = get_json(s, SEARCH, params=params)
            page = data.get("projects") or []
            fresh = [p for p in page if (p.get("publicationDate") or "") >= since_s]
            for p in fresh:
                items[p.get("publicationId") or p.get("publicationNumber")] = p
            last = (data.get("pagination") or {}).get("lastItem")
            if not page or not last or len(fresh) < len(page):
                break  # newest-first: once we see older items, the rest is older too
        log.info("simap %r: %d unique publications so far", q, len(items))

    out: list[Tender] = []
    for n, it in enumerate(items.values()):
        detail = None
        if n < MAX_DETAILS and it.get("id") and it.get("publicationId"):
            time.sleep(SLEEP)
            calls += 1
            try:
                detail = get_json(s, DETAIL.format(pid=it["id"], pub=it["publicationId"]))
            except Exception as e:  # noqa: BLE001 — keep the search hit even without details
                log.warning("simap detail %s failed: %s", it.get("publicationNumber"), e)
        t = to_tender(it, detail)
        if t.source_id:
            out.append(t)
    log.info("simap: %d API calls, %d publications", calls, len(out))
    return out
