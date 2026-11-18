"""France — BOAMP (Bulletin officiel des annonces des marchés publics), DILA open data.

Opendatasoft Explore API v2.1, no key (verified with tools/probe_more.py, Nov 2026):
  GET https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records
      ?where=<ODSQL>&order_by=dateparution desc&limit=100&offset=N
Full-text: a quoted string in `where` searches all fields, e.g. "BPF" AND "validation".
Fields: idweb, objet, nomacheteur, dateparution, datelimitereponse, titulaire, procedure_libelle,
nature_libelle (Avis de marché / Résultat de marché), descripteur_libelle, url_avis, donnees (JSON text).
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import date

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
PAGE = 100
MAX_OFFSET = 2000
SLEEP = 0.5

QUERIES = [
    '"systèmes informatisés"',
    '"système informatisé"',
    '"GAMP"',
    '"annexe 11"',
    '"21 CFR"',
    '"validation" AND ("BPF" OR "bonnes pratiques de fabrication" OR "pharmaceutique")',
    '"qualification" AND ("BPF" OR "bonnes pratiques de fabrication")',
    '"LIMS"',
    '"radiopharmacie"',
]
_STRIP = re.compile(r"[{}\[\]\"]|\b[A-Za-z_]+:\s")


def _text_from_donnees(raw) -> str:
    """`donnees` is a JSON string of the full notice; keep only human-readable values."""
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return ""
    vals: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and len(o) > 25 and not o.startswith("http"):
            vals.append(o)
    walk(obj)
    return " ".join(dict.fromkeys(vals))


def _cpv(raw) -> list[str]:
    return sorted(set(re.findall(r"\b(\d{8})(?:-\d)?\b", str(raw or ""))))[:10]


def to_tender(r: dict) -> Tender:
    desc = _text_from_donnees(r.get("donnees"))
    nature = r.get("nature_libelle") or r.get("nature") or ""
    return Tender(
        source="boamp",
        source_id=str(r.get("idweb") or r.get("id") or ""),
        title=r.get("objet") or "",
        url=r.get("url_avis") or (f"https://www.boamp.fr/pages/avis/?q=idweb:{r.get('idweb')}" if r.get("idweb") else ""),
        description=(" ".join(r.get("descripteur_libelle") or []) + " " + desc)[:3000],
        buyer=r.get("nomacheteur") or "",
        country="FRA",
        published=str(r.get("dateparution") or "")[:10],
        deadline=str(r.get("datelimitereponse") or "")[:16].replace("T", " "),
        notice_type=nature,
        cpv=_cpv(r.get("donnees")),
        winners=[w for w in (r.get("titulaire") or []) if w][:10],
        tender_id=f"boamp:{r['contractfolderid']}" if r.get("contractfolderid") else "",
        procedure=r.get("procedure_libelle") or "",
    )


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    calls = 0
    for q in QUERIES:
        where = f"({q}) AND dateparution >= date'{since.isoformat()}'"
        for offset in range(0, MAX_OFFSET, PAGE):
            time.sleep(SLEEP)
            calls += 1
            data = get_json(s, URL, params={"where": where, "order_by": "dateparution desc",
                                            "limit": PAGE, "offset": offset})
            res = data.get("results") or []
            for r in res:
                t = to_tender(r)
                if t.source_id:
                    out[t.key] = t
            if len(res) < PAGE:
                break
        log.info("boamp %s: %d unique so far", q, len(out))
    log.info("boamp: %d API calls, %d notices", calls, len(out))
    return list(out.values())
