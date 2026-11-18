"""Polish e-Zamówienia / Biuletyn Zamówień Publicznych (BZP).

Public board API (no auth), used by the ezamowienia.gov.pl search UI:
  GET https://ezamowienia.gov.pl/mo-board/api/v1/notice
      ?NoticeType=ContractNotice&PublicationDateFrom=...&PublicationDateTo=...&PageSize=..&PageNumber=..

Field names are not formally documented; parsing is defensive and logs the keys of the
first record so mismatches are easy to fix from the Actions log.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from ..http import get_json
from ..models import Tender

log = logging.getLogger(__name__)

URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
NOTICE_TYPES = ["ContractNotice", "TenderResultNotice"]
PAGE_SIZE = 500
MAX_PAGES = 40
TAG_RE = re.compile(r"<[^>]+>")


def _first(d: dict, *keys, default=""):
    for k in keys:
        if d.get(k) not in (None, "", []):
            return d[k]
    return default


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
    )


def fetch(s, since: date) -> list[Tender]:
    out: dict[str, Tender] = {}
    to = date.today() + timedelta(days=1)
    logged_keys = False
    for nt in NOTICE_TYPES:
        for page in range(1, MAX_PAGES + 1):
            params = {
                "NoticeType": nt,
                "PublicationDateFrom": f"{since.isoformat()}T00:00:00",
                "PublicationDateTo": f"{to.isoformat()}T00:00:00",
                "PageSize": PAGE_SIZE,
                "PageNumber": page,
            }
            data = get_json(s, URL, params=params)
            items = data if isinstance(data, list) else (data.get("items") or data.get("data") or [])
            if items and not logged_keys:
                log.info("ezamowienia record keys: %s", sorted(items[0].keys()))
                logged_keys = True
            for n in items:
                t = to_tender(n)
                if t.source_id:
                    out[t.key] = t
            log.info("ezamowienia %s page %d: %d", nt, page, len(items))
            if len(items) < PAGE_SIZE:
                break
    return list(out.values())
