"""Diagnostic: simap.ch public search API shape (endpoint seen in the site's own network traffic)."""
import json
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}
BASE = "https://www.simap.ch/rest/publications/v2/project/project-search"


def show(label, params):
    time.sleep(1.5)
    r = requests.get(BASE, params=params, headers=H, timeout=60)
    print(f"\n=== {label}: HTTP {r.status_code}")
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        print("not json:", r.text[:300])
        return None
    if isinstance(j, dict):
        for k, v in j.items():
            if isinstance(v, list):
                print(f"list {k} len={len(v)}")
                if v and isinstance(v[0], dict):
                    print("item keys:", sorted(v[0].keys()))
                    print("first:", json.dumps(v[0], ensure_ascii=False)[:2500])
            else:
                print(f"{k} = {json.dumps(v, ensure_ascii=False)[:400]}")
    return j


langs = [("lang", x) for x in ("de", "fr", "it", "en")]
j = show("search GMP", [("search", "GMP"), *langs, ("orderAddressCountryOnlySwitzerland", "false")])
show("search Validierung", [("search", "Validierung"), *langs])
show("search GAMP", [("search", "GAMP"), *langs])

# pagination candidates
if isinstance(j, dict):
    pag = j.get("pagination") or {}
    print("\npagination object:", pag)
    last = pag.get("lastItem") or pag.get("lastItemId")
    if last:
        show("page 2 via lastItem", [("search", "GMP"), *langs, ("lastItem", last)])

# detail endpoint candidates
if isinstance(j, dict):
    items = next((v for v in j.values() if isinstance(v, list) and v), [])
    if items:
        it = items[0]
        pid = it.get("id") or it.get("projectId")
        pubid = (it.get("publicationId") or (it.get("latestPublication") or {}).get("id")
                 or (it.get("publication") or {}).get("id"))
        for path in [f"https://www.simap.ch/rest/publications/v1/project/{pid}/publication-details/{pubid}",
                     f"https://www.simap.ch/rest/publications/v2/project/{pid}/publication-details/{pubid}",
                     f"https://www.simap.ch/rest/publications/v1/project/{pid}"]:
            time.sleep(1.5)
            r = requests.get(path, headers=H, timeout=60)
            print(f"\nDETAIL {path}: HTTP {r.status_code}")
            if r.status_code == 200:
                d = r.json()
                print("detail keys:", sorted(d.keys()) if isinstance(d, dict) else type(d))
                print(json.dumps(d, ensure_ascii=False)[:3000])
                break
