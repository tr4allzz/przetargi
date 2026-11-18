"""Diagnostic: Baza Konkurencyjności search API shape and Find a Tender response time."""
import json
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}

BK = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/api/announcements/search"
for label, params in {
    "bk published walidacja": {"page": 1, "limit": 5, "sort": "default", "query": "walidacja",
                               "status[0]": "PUBLISHED"},
    "bk page2": {"page": 2, "limit": 5, "sort": "default", "query": "walidacja", "status[0]": "PUBLISHED"},
    "bk closed": {"page": 1, "limit": 2, "sort": "default", "query": "walidacja", "status[0]": "CLOSED"},
    "bk resolved": {"page": 1, "limit": 2, "sort": "default", "query": "walidacja", "status[0]": "RESOLVED"},
}.items():
    time.sleep(2)
    r = requests.get(BK, params=params, headers=H, timeout=60)
    print(f"{label}: HTTP {r.status_code}")
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        print("  not json:", r.text[:300])
        continue
    if isinstance(j, dict):
        print("  top keys:", list(j.keys()))
        for k, v in j.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                print(f"  list '{k}' len={len(v)} item keys:", sorted(v[0].keys()))
                print("  first item:", json.dumps(v[0], ensure_ascii=False)[:1500])
            elif not isinstance(v, (list, dict)):
                print(f"  {k} = {v}")
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    if isinstance(v2, list) and v2 and isinstance(v2[0], dict):
                        print(f"  data.{k2} len={len(v2)} keys:", sorted(v2[0].keys()))
                        print("  first:", json.dumps(v2[0], ensure_ascii=False)[:2500])
                    else:
                        print(f"  data.{k2} =", json.dumps(v2, ensure_ascii=False)[:300])

