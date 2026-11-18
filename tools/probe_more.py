"""Diagnostic: Germany (oeffentlichevergabe.de), France (BOAMP), Czechia (ISVZ open data)."""
import io
import json
import time
import zipfile

import requests

H = {"User-Agent": "przetargi-probe/0.1 (+https://github.com/tr4allzz/przetargi)"}


def flat(o, p="", depth=0):
    if depth > 8:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flat(v, f"{p}.{k}" if p else k, depth + 1)
    elif isinstance(o, list):
        if o:
            yield from flat(o[0], p + "[0]", depth + 1)
    else:
        yield p, o


# --- Germany ---------------------------------------------------------------
print("=== DE oeffentlichevergabe.de")
for fmt in ("ocds.zip",):
    url = "https://oeffentlichevergabe.de/api/notice-exports"
    t0 = time.time()
    r = requests.get(url, params={"pubDay": "2026-11-16", "format": fmt}, headers=H, timeout=120)
    print(f"{fmt}: HTTP {r.status_code}, {len(r.content)} bytes in {time.time()-t0:.1f}s, type={r.headers.get('content-type')}")
    if r.ok:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        print("files:", len(names), names[:3])
        data = json.loads(z.read(names[0]))
        if isinstance(data, dict):
            print("top keys:", list(data.keys()))
            rels = data.get("releases") or []
            print("releases in first file:", len(rels))
            if rels:
                for k, v in flat(rels[0]):
                    print("  ", k, "=", json.dumps(v, ensure_ascii=False)[:140])

# --- France ----------------------------------------------------------------
print("\n=== FR BOAMP")
base = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
for where in ['search("validation") AND search("GMP")', '"BPF"', 'search("qualification") AND search("pharmac")']:
    time.sleep(1)
    r = requests.get(base, params={"where": where, "limit": 3, "order_by": "dateparution desc"}, headers=H, timeout=60)
    print(f"where {where!r}: HTTP {r.status_code}")
    if r.ok:
        j = r.json()
        print("  total_count:", j.get("total_count"))
        res = j.get("results") or []
        if res:
            for k, v in res[0].items():
                if k in ("donnees", "gestion"):
                    print(f"  {k} = <{len(str(v))} chars> {str(v)[:200]}")
                else:
                    print(f"  {k} = {json.dumps(v, ensure_ascii=False)[:160]}")
    else:
        print("  ", r.text[:300])

# --- Czechia ---------------------------------------------------------------
print("\n=== CZ ISVZ open data")
for url in ["https://isvz.nipez.cz/opendata/nova", "https://isvz.nipez.cz/opendata"]:
    time.sleep(1)
    r = requests.get(url, headers=H, timeout=60)
    print(f"{url}: HTTP {r.status_code} type={r.headers.get('content-type')} len={len(r.text)}")
    import re
    links = sorted(set(re.findall(r'href="([^"]+(?:json|zip|xml)[^"]*)"', r.text)))
    print("  data links:", links[:25])
