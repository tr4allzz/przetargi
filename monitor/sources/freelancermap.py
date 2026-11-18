"""freelancermap.de — freelance / contracting gigs (not public tenders).

Keyword pages /projekte/<slug> are server-rendered and embed the search result as JSON:
  <script type="application/json" class="js-react-on-rails-component" data-component-name="ProjectSearch">
  -> initialState.result.projects[]: id, slug, title, description (HTML), company, city,
     country.iso2, created (ISO), contractType, duration (months), beginningText,
     projectContractType.{type, remoteInPercent}, skills[], links.project
robots.txt allows generic crawlers (verified Nov 2026). Each page lists ~20–25 newest gigs;
we fetch a handful of keyword pages once per run with a pause between requests.
"""
from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import date

from ..models import Tender

log = logging.getLogger(__name__)

BASE = "https://www.freelancermap.de"
SLUGS = ["csv", "gxp", "gmp", "gamp", "validierung", "computervalidierung", "qualifizierung",
         "annex-11", "lims", "pharma"]
SLEEP = 2.0
COMPONENT = re.compile(r'data-component-name="ProjectSearch"[^>]*>(.*?)</script>', re.S)
TAG = re.compile(r"<[^>]+>")
CONTRACT = {"contracting": "kontrakt (freelance)", "employee_leasing": "ANÜ (leasing pracownika)",
            "permanent": "etat", "permanent_position": "etat", "freelance": "freelance"}


def _clean(s: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", s or "")).split())


def to_tender(p: dict) -> Tender:
    pct = (p.get("projectContractType") or {})
    remote = pct.get("remoteInPercent")
    where = (p.get("city") or "").strip()
    if remote is not None:
        where = (f"{where}, " if where else "") + ("100% remote" if remote == 100 else f"remote {remote}%")
    skills = [s.get("de") or s.get("en") for s in (p.get("skills") or []) if isinstance(s, dict)]
    link = ((p.get("links") or {}).get("project")) or f"/projekt/{p.get('slug', '')}"
    dur = p.get("duration")
    budget = p.get("budget") or {}
    cents = budget.get("amountInCents") if isinstance(budget, dict) else None
    cur = ((budget.get("currency") or {}).get("code") if isinstance(budget, dict) else "") or "EUR"
    return Tender(
        source="freelancermap",
        source_id=str(p.get("id")),
        title=_clean(p.get("title")),
        url=BASE + link if link.startswith("/") else link,
        description=_clean(p.get("description")) + (" Skills: " + ", ".join(filter(None, skills)) if skills else ""),
        buyer=(p.get("company") or "").strip(),
        country=((p.get("country") or {}).get("iso2") or ""),
        published=(p.get("created") or "")[:10],
        notice_type="zlecenie",
        estimated_value=f"budżet {cents / 100:,.0f} {cur}".replace(",", " ") if cents else "",
        procedure=" · ".join(filter(None, [CONTRACT.get(pct.get("type"), pct.get("type") or ""), where])),
        duration=" · ".join(filter(None, [f"start: {p['beginningText']}" if p.get("beginningText") else "",
                                          f"{dur} mies." if dur else ""])),
    )


def parse_page(text: str) -> list[dict]:
    m = COMPONENT.search(text)
    if not m:
        return []
    data = json.loads(html.unescape(m.group(1)))
    return ((data.get("initialState") or {}).get("result") or {}).get("projects") or []


def fetch(s, since: date) -> list[Tender]:
    since_s = since.isoformat()
    out: dict[str, Tender] = {}
    for slug in SLUGS:
        time.sleep(SLEEP)
        r = s.get(f"{BASE}/projekte/{slug}", timeout=45, headers={"Accept": "text/html"})
        if r.status_code == 404:
            log.info("freelancermap: no page for %s", slug)
            continue
        r.raise_for_status()
        projects = parse_page(r.text)
        fresh = 0
        for p in projects:
            t = to_tender(p)
            if t.published and t.published < since_s:
                continue
            out.setdefault(t.source_id, t)
            fresh += 1
        log.info("freelancermap %s: %d projects, %d in window", slug, len(projects), fresh)
    return list(out.values())
