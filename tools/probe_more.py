"""Diagnostic round 3: Austria data.gv.at Kerndaten datasets -> KDQ -> Kerndaten XML; freelancermap project fields."""
import html
import json
import re
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1 (+https://github.com/tr4allzz/przetargi)"}


def get(url, **kw):
    time.sleep(0.7)
    try:
        return requests.get(url, headers=H, timeout=60, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"  ERR {url}: {type(e).__name__}: {str(e)[:150]}")
        return None


print("=== AT search counts")
S = "https://www.data.gv.at/api/hub/search/search"
for q in ["Kerndaten", "Kerndatenquelle", "Ausschreibung", "eForms"]:
    r = get(S, params={"q": q, "limit": 1, "filter": "dataset"})
    if r is not None and r.ok:
        print(q, "->", r.json()["result"]["count"])
r = get(S, params={"q": "Kerndatenquelle", "limit": 3, "filter": "dataset"})
res = r.json()["result"]["results"] if r is not None and r.ok else []
for d in res:
    print("\nDATASET", d.get("resource"))
    print("  title:", json.dumps(d.get("title"), ensure_ascii=False)[:200])
    print("  publisher:", json.dumps(d.get("publisher"), ensure_ascii=False)[:200])
    print("  keys:", sorted(d.keys()))
    for dist in (d.get("distributions") or [])[:3]:
        print("  dist:", json.dumps({k: dist.get(k) for k in ("format", "access_url", "download_url", "title")}, ensure_ascii=False)[:400])
    # follow first distribution URL
    for dist in (d.get("distributions") or [])[:1]:
        url = dist.get("access_url") or dist.get("download_url")
        if isinstance(url, list):
            url = url[0]
        if url:
            rr = get(url)
            if rr is not None:
                print(f"  KDQ {url}: HTTP {rr.status_code} type={rr.headers.get('content-type')} len={len(rr.text)}")
                print("  KDQ head:", rr.text[:1200].replace("\n", " "))
                links = re.findall(r"<(?:url|link|loc)[^>]*>([^<]+)</", rr.text)[:2]
                for l in links:
                    r3 = get(l.strip())
                    if r3 is not None:
                        print(f"   KD {l.strip()}: HTTP {r3.status_code} len={len(r3.text)}")
                        print("   KD head:", re.sub(r"\s+", " ", r3.text[:1500]))

print("\n=== freelancermap project fields")
r = get("https://www.freelancermap.de/projekte/gxp")
m = re.search(r'data-component-name="ProjectSearch"[^>]*>(.*?)</script>', r.text, re.S) if r is not None else None
if m:
    data = json.loads(html.unescape(m.group(1)))
    projects = data["initialState"]["result"]["projects"]
    print("count:", len(projects), "| result keys:", sorted(data["initialState"]["result"].keys()))
    p = projects[0]
    for k, v in p.items():
        if k in ("poster",):
            continue
        print(f"  {k} = {json.dumps(v, ensure_ascii=False)[:150]}")
