"""Diagnostic: Baza Konkurencyjności search API shape and Find a Tender response time."""
import json
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}

BK = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl/api/announcements/search"
for label, params in {
    "bk published walidacja": {"page": 1, "limit": 5, "sort": "default", "query": "walidacja",
                               "status[0]": "PUBLISHED"},
    "bk all-status walidacja": {"page": 1, "limit": 5, "sort": "default", "query": "walidacja"},
    "bk page2": {"page": 2, "limit": 5, "sort": "default", "query": "walidacja"},
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
                print(f"  dict '{k}':", json.dumps(v, ensure_ascii=False)[:400])

FTS = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
for limit in (5, 50):
    t0 = time.time()
    try:
        r = requests.get(FTS, params={"updatedFrom": "2026-11-17T00:00:00",
                                      "updatedTo": "2026-11-18T00:00:00", "limit": limit},
                         headers=H, timeout=180)
        j = r.json()
        print(f"fts limit={limit}: HTTP {r.status_code} in {time.time()-t0:.1f}s, "
              f"releases={len(j.get('releases') or [])}, next={'next' in (j.get('links') or {})}")
    except Exception as e:  # noqa: BLE001
        print(f"fts limit={limit}: {type(e).__name__} after {time.time()-t0:.1f}s: {e}")
