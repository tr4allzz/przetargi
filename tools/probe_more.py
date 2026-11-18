"""Diagnostic: Czechia (ISVZ open data), Austria (data.gv.at Kerndaten), freelancermap (robots + page shape)."""
import json
import re
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1 (+https://github.com/tr4allzz/przetargi)"}


def get(url, **kw):
    time.sleep(1)
    try:
        r = requests.get(url, headers=H, timeout=90, **kw)
        return r
    except Exception as e:  # noqa: BLE001
        print(f"  ERR {url}: {e}")
        return None


print("=== CZ ISVZ")
for url in ["https://isvz.nipez.cz/opendata", "https://isvz.nipez.cz/opendata/nova"]:
    r = get(url)
    if r is None:
        continue
    print(f"{url}: HTTP {r.status_code} len={len(r.text)}")
    links = sorted(set(re.findall(r'href="([^"#]+)"', r.text)))
    print("  links:", [l for l in links if any(x in l.lower() for x in ("opendata", ".json", ".zip", "api", "download", "soubor"))][:40])
    print("  text sample:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:1200])

print("\n=== AT data.gv.at")
for url, params in [
    ("https://www.data.gv.at/katalog/api/3/action/package_search", {"q": "Kerndaten", "rows": 3}),
    ("https://www.data.gv.at/katalog/api/3/action/package_search", {"q": "eForms Bekanntmachung", "rows": 3}),
    ("https://www.data.gv.at/katalog/api/3/action/package_search", {"fq": "tags:Vergabe", "rows": 3}),
]:
    r = get(url, params=params)
    if r is None:
        continue
    print(f"{params}: HTTP {r.status_code}")
    try:
        j = r.json()
        res = j.get("result") or {}
        print("  count:", res.get("count"))
        for p in (res.get("results") or [])[:3]:
            print("  pkg:", p.get("name"), "|", p.get("title"), "| org:", (p.get("organization") or {}).get("title"))
            for res_ in (p.get("resources") or [])[:3]:
                print("     res:", res_.get("format"), res_.get("url"))
            print("     extras:", [(e.get("key"), str(e.get("value"))[:80]) for e in (p.get("extras") or [])][:12])
    except ValueError:
        print("  not json:", r.text[:300])

print("\n=== freelancermap")
for url in ["https://www.freelancermap.de/robots.txt", "https://www.freelancermap.com/robots.txt"]:
    r = get(url)
    if r is not None:
        print(f"{url}: HTTP {r.status_code}\n{r.text[:1500]}")
r = get("https://www.freelancermap.de/projektboerse.html", params={"query": "GMP Validierung"})
if r is not None:
    print(f"search page: HTTP {r.status_code} final={r.url} len={len(r.text)}")
    print("  json blobs:", re.findall(r'<script[^>]+type="application/(?:ld\+)?json"[^>]*>', r.text)[:5])
    print("  next-data:", "__NEXT_DATA__" in r.text, "| nuxt:", "__NUXT__" in r.text)
    print("  project links:", sorted(set(re.findall(r'href="(/projekt/[^"]+)"', r.text)))[:10])
r = get("https://www.freelancermap.de/projekte/csv")
if r is not None:
    print(f"/projekte/csv: HTTP {r.status_code} len={len(r.text)} links:",
          sorted(set(re.findall(r'href="(?:https://www\.freelancermap\.de)?(/projekt/[^"]+)"', r.text)))[:10])
