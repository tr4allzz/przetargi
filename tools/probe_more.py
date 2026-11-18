"""Diagnostic round 2: freelancermap ProjectSearch JSON, CZ alternatives, AT data.gv.at/USP endpoints."""
import html
import json
import re
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1 (+https://github.com/tr4allzz/przetargi)",
     "Accept": "text/html,application/json"}


def get(url, **kw):
    time.sleep(1)
    try:
        return requests.get(url, headers=H, timeout=60, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"  ERR {url}: {type(e).__name__}: {str(e)[:150]}")
        return None


def keys_tree(o, p="", depth=0, out=None, limit=80):
    out = out if out is not None else []
    if len(out) >= limit or depth > 6:
        return out
    if isinstance(o, dict):
        for k, v in o.items():
            keys_tree(v, f"{p}.{k}" if p else k, depth + 1, out, limit)
    elif isinstance(o, list):
        out.append(f"{p}[] len={len(o)}")
        if o:
            keys_tree(o[0], p + "[0]", depth + 1, out, limit)
    else:
        out.append(f"{p} = {json.dumps(o, ensure_ascii=False)[:100]}")
    return out


print("=== freelancermap ProjectSearch JSON")
r = get("https://www.freelancermap.de/projekte/csv")
if r is not None:
    m = re.search(r'data-component-name="ProjectSearch"[^>]*>(.*?)</script>', r.text, re.S)
    if m:
        data = json.loads(html.unescape(m.group(1)))
        for line in keys_tree(data, limit=120):
            print("  ", line)

print("\n=== CZ alternatives")
for url in ["https://zakazky.gov.cz/", "https://nen.nipez.cz/", "https://vvz.nipez.cz/",
            "https://www.hlidacstatu.cz/api/v2/verejnezakazky/hledat?dotaz=validace"]:
    r = get(url)
    if r is not None:
        print(f"{url}: HTTP {r.status_code} len={len(r.text)} api-hints:",
              sorted(set(re.findall(r'["\'](/api/[^"\']{3,80})["\']', r.text)))[:10])

print("\n=== AT")
for url, params in [
    ("https://www.data.gv.at/api/hub/search/search", {"q": "Kerndaten", "limit": 2}),
    ("https://www.data.gv.at/api/hub/search/search", {"q": "Vergabe", "limit": 2, "filter": "dataset"}),
    ("https://www.usp.gv.at/ausschreibungssuche", {}),
    ("https://www.usp.gv.at/foerderungen-ausschreibungen/ausschreibungssuche.html", {}),
]:
    r = get(url, params=params)
    if r is None:
        continue
    print(f"{url} {params}: HTTP {r.status_code} type={r.headers.get('content-type')} len={len(r.text)}")
    if "json" in (r.headers.get("content-type") or ""):
        for line in keys_tree(r.json(), limit=40):
            print("  ", line)
    else:
        print("  links:", sorted(set(re.findall(r'href="([^"]*(?:ausschreib|suche|kerndaten|api)[^"]*)"', r.text, re.I)))[:15])
