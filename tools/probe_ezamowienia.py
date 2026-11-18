"""Diagnostic: which query parameters does the e-Zamówienia board API honour?

Prints, for each variant, the number of records and min/max publicationDate.
Run manually via the 'Probe' workflow.
"""
import json
import time

import requests

URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}

VARIANTS = {
    "A day T00 size50": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16T00:00:00",
                         "PublicationDateTo": "2026-11-17T00:00:00", "PageSize": 50},
    "B same page2": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16T00:00:00",
                     "PublicationDateTo": "2026-11-17T00:00:00", "PageSize": 50, "PageNumber": 2},
    "C date only": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16",
                    "PublicationDateTo": "2026-11-17", "PageSize": 50},
    "D no date": {"NoticeType": "ContractNotice", "PageSize": 50},
    "E 6h size500": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16T00:00:00",
                     "PublicationDateTo": "2026-11-16T06:00:00", "PageSize": 500},
    "F day size500": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16T00:00:00",
                      "PublicationDateTo": "2026-11-17T00:00:00", "PageSize": 500},
    "G camelCase": {"noticeType": "ContractNotice", "publicationDateFrom": "2026-11-16T00:00:00",
                    "publicationDateTo": "2026-11-17T00:00:00", "pageSize": 50, "pageNumber": 2},
    "H SearchAfter": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-11-16T00:00:00",
                      "PublicationDateTo": "2026-11-17T00:00:00", "PageSize": 50,
                      "SearchAfter": "2026-11-16T12:00:00"},
    "I OrderObject": {"NoticeType": "ContractNotice", "PublicationDateFrom": "2026-10-01T00:00:00",
                      "PublicationDateTo": "2026-11-17T00:00:00", "PageSize": 50,
                      "OrderObject": "walidacja"},
}

for name, params in VARIANTS.items():
    time.sleep(2)
    try:
        r = requests.get(URL, params=params, headers=H, timeout=60)
        if r.status_code != 200:
            print(f"{name}: HTTP {r.status_code} {r.text[:200]}")
            continue
        j = r.json()
        a = j if isinstance(j, list) else (j.get("items") or [])
        ds = sorted((x.get("publicationDate") or "")[:16] for x in a)
        first = a[0].get("bzpNumber") if a else None
        titles = [x.get("orderObject", "")[:60] for x in a[:3]]
        print(f"{name}: n={len(a)} min={ds[0] if ds else None} max={ds[-1] if ds else None} "
              f"first={first} titles={json.dumps(titles, ensure_ascii=False)}")
        if not isinstance(j, list):
            print(f"   envelope keys: {list(j.keys())}")
    except Exception as e:  # noqa: BLE001
        print(f"{name}: ERR {e}")
