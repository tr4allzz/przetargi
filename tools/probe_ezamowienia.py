"""Diagnostic: which query parameters does the e-Zamówienia board API honour?

Prints, for each variant, the number of records and min/max publicationDate.
Run manually via the 'Probe' workflow.
"""
import json
import time

import requests

URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}

BASE = {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16",
        "PublicationDateTo": "2026-11-16", "PageSize": 50}
VARIANTS = {
    "A base": dict(BASE),
    "J SearchAfter=last objectId": "AFTER_OBJECTID",
    "K SearchAfter=last bzpNumber": "AFTER_BZP",
    "L OrderObject=Dostawa": {**BASE, "OrderObject": "Dostawa"},
    "M OrderObject=walidacji (Oct-Nov)": {**BASE, "PublicationDateFrom": "2026-09-01",
                                         "PublicationDateTo": "2026-11-17", "OrderObject": "walidacj"},
    "N CpvCode=72225000 (Jan-Nov)": {**BASE, "PublicationDateFrom": "2026-01-01",
                                    "PublicationDateTo": "2026-11-17", "CpvCode": "72225000-8"},
    "O From=To same day count500": {**BASE, "PageSize": 500},
}

last = None
for name, params in VARIANTS.items():
    time.sleep(2)
    if params in ("AFTER_OBJECTID", "AFTER_BZP"):
        key = "objectId" if params == "AFTER_OBJECTID" else "bzpNumber"
        params = {**BASE, "SearchAfter": (last or {}).get(key)}
    try:
        r = requests.get(URL, params=params, headers=H, timeout=60)
        if r.status_code != 200:
            print(f"{name}: HTTP {r.status_code} {r.text[:200]}")
            continue
        j = r.json()
        a = j if isinstance(j, list) else (j.get("items") or [])
        ds = sorted((x.get("publicationDate") or "")[:16] for x in a)
        first = a[0].get("bzpNumber") if a else None
        if name.startswith("A") and a:
            last = a[-1]
            print(f"   last record objectId={last.get('objectId')} bzp={last.get('bzpNumber')}")
        titles = [x.get("orderObject", "")[:60] for x in a[:3]]
        print(f"{name}: n={len(a)} min={ds[0] if ds else None} max={ds[-1] if ds else None} "
              f"first={first} titles={json.dumps(titles, ensure_ascii=False)}")
        if not isinstance(j, list):
            print(f"   envelope keys: {list(j.keys())}")
    except Exception as e:  # noqa: BLE001
        print(f"{name}: ERR {e}")
