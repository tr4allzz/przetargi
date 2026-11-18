"""Probe round 4: historical depth (e-Zamówienia 2021–2025, TED legacy notices) and freelancermap detail rates."""
import json
import re
import sys
import time

import requests

sys.path.insert(0, ".")
from monitor.sources import ted  # noqa: E402

H = {"User-Agent": "przetargi-probe/0.1 (+https://github.com/tr4allzz/przetargi)", "Accept": "application/json"}

print("=== e-Zamowienia by year (OrderObject=walidac)")
for y in range(2020, 2026):
    for half, (a, b) in enumerate([(f"{y}-01-01", f"{y}-06-30"), (f"{y}-07-01", f"{y}-12-31")]):
        time.sleep(1.5)
        try:
            r = requests.get("https://ezamowienia.gov.pl/mo-board/api/v1/notice", headers=H, timeout=60, params={
                "NoticeType": "TenderResultNotice", "PublicationDateFrom": a, "PublicationDateTo": b,
                "OrderObject": "walidac", "PageSize": 100})
            js = r.json() if r.ok else None
            n = len(js) if isinstance(js, list) else (js or {})
            first = js[0] if isinstance(js, list) and js else {}
            print(y, half, "HTTP", r.status_code, "n=", n if isinstance(n, int) else str(n)[:120],
                  "| sample:", (first.get("orderObject") or "")[:80], first.get("publicationDate"),
                  "| body len", len(first.get("htmlBody") or ""))
        except Exception as e:  # noqa: BLE001
            print(y, half, "ERR", e)

print("\n=== TED legacy")
for y in (2016, 2019, 2021, 2022, 2023):
    q = f'FT~"computerised system validation" AND publication-date>={y}0101 AND publication-date<={y}1231'
    time.sleep(1)
    r = requests.post("https://api.ted.europa.eu/v3/notices/search", headers=H, timeout=60,
                      json={"query": q, "fields": ted.FIELDS, "limit": 5, "page": 1, "scope": "ALL",
                            "paginationMode": "PAGE_NUMBER"})
    print(y, "HTTP", r.status_code, r.text[:200] if not r.ok else "")
    if r.ok:
        js = r.json()
        print("  total", js.get("totalNoticeCount"))
        for n in js.get("notices", [])[:3]:
            filled = {k: v for k, v in n.items() if v not in (None, "", [], {})}
            print("  ", json.dumps(filled, ensure_ascii=False)[:700])
# legacy award notices with the generic validation/qualification query
q = 'FT~"validation" AND FT~"GMP" AND notice-type IN (can-standard) AND publication-date>=20150101 AND publication-date<=20221231'
r = requests.post("https://api.ted.europa.eu/v3/notices/search", headers=H, timeout=60,
                  json={"query": q, "fields": ted.FIELDS + ["notice-type", "form-type"], "limit": 5, "page": 1,
                        "scope": "ALL", "paginationMode": "PAGE_NUMBER"})
print("legacy CAN:", r.status_code, r.text[:300] if not r.ok else r.json().get("totalNoticeCount"))
if r.ok:
    for n in r.json().get("notices", [])[:3]:
        print("  ", json.dumps({k: v for k, v in n.items() if v not in (None, "", [], {})}, ensure_ascii=False)[:900])

print("\n=== freelancermap detail pages")
for slug in ["1085300-csv-experte-pharma", "senior-gxp-consultant", "freelancer-qualification-csv-specialist-gn-gmp-pharma",
             "100-prozent-remote-nearshore-senior-gxp-consultant-m-f-d"]:
    time.sleep(2)
    r = requests.get(f"https://www.freelancermap.de/projekt/{slug}", headers={**H, "Accept": "text/html"}, timeout=60)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    hits = sorted(set(m.group(0) for m in re.finditer(
        r"(?i)(stundensatz|tagessatz|vergütung|budget|rate)[^.]{0,60}|\d{2,4}\s?(€|eur)[^.]{0,30}", txt)))[:8]
    comps = re.findall(r'data-component-name="([^"]+)"', r.text)
    print(slug, r.status_code, "components:", comps, "\n   hits:", hits)
    m = re.search(r'data-component-name="ProjectShow"[^>]*>(.*?)</script>', r.text, re.S) or \
        re.search(r'data-component-name="Project[^"]*"[^>]*>(.*?)</script>', r.text, re.S)
    if m:
        import html as h
        try:
            d = json.loads(h.unescape(m.group(1)))
            def walk(o, p=""):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if re.search(r"(?i)rate|budget|salary|price|hour|satz", k):
                            print("   key", p + k, "=", json.dumps(v, ensure_ascii=False)[:120])
                        walk(v, p + k + ".")
                elif isinstance(o, list) and o:
                    walk(o[0], p + "[0].")
            walk(d)
        except Exception as e:  # noqa: BLE001
            print("   json err", e)
