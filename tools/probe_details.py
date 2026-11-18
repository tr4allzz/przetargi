"""Diagnostic: which award/value fields are available in TED API and e-Zamówienia htmlBody."""
import json
import re
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}
TED = "https://api.ted.europa.eu/v3/notices/search"

CANDIDATES = [
    "estimated-value-lot", "estimated-value-cur-lot", "estimated-value-proc", "estimated-value-glo",
    "tender-value", "tender-value-cur", "tender-value-lowest", "tender-value-highest",
    "result-value-lot", "result-value-notice", "notice-value", "total-value", "contract-value",
    "received-submissions-count", "received-submissions-type-val", "received-submissions-type-code",
    "winner-name", "winner-country", "winner-size", "procedure-type", "award-criterion-type-lot",
    "award-criterion-number-weight-lot", "award-criterion-name-lot", "framework-agreement-lot",
    "duration-period-value-lot", "duration-period-unit-lot", "contract-conclusion-date",
    "BT-27-Lot", "BT-720-Tender", "BT-759-LotResult", "BT-711-LotResult", "BT-710-LotResult",
]

# 1) find a query syntax that targets one notice
for q in ['publication-number=747344-2026', 'ND=747344-2026', 'publication-number="747344-2026"']:
    time.sleep(1)
    r = requests.post(TED, json={"query": q, "fields": ["publication-number"], "limit": 1}, headers=H, timeout=60)
    print(f"query {q!r}: HTTP {r.status_code} {r.text[:200]}")

# 2) test each field individually on award notices (heidelberg + amgros + armee)
Q = 'publication-number IN (747344-2026 814489-2025 747183-2026)'
ok = []
for f in CANDIDATES:
    time.sleep(0.7)
    r = requests.post(TED, json={"query": Q, "fields": ["publication-number", f], "limit": 5}, headers=H, timeout=60)
    if r.status_code != 200:
        print(f"FIELD {f}: HTTP {r.status_code} {r.text[:160]}")
        continue
    vals = [n.get(f) for n in r.json().get("notices", [])]
    print(f"FIELD {f}: OK {json.dumps(vals, ensure_ascii=False)[:300]}")
    ok.append(f)
print("VALID FIELDS:", ok)

# 3) e-Zamówienia: dump key sections of a result notice and a contract notice
EZ = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"
TAG = re.compile(r"<[^>]+>")
for nt, frm, to, title in [("TenderResultNotice", "2026-03-13", "2026-03-13", "biobank"),
                           ("ContractNotice", "2026-02-05", "2026-02-05", "biobank")]:
    time.sleep(1)
    r = requests.get(EZ, params={"NoticeType": nt, "PublicationDateFrom": frm, "PublicationDateTo": to,
                                 "PageSize": 50, "OrderObject": title}, headers=H, timeout=60)
    items = r.json()
    print(f"\n=== {nt}: {len(items)} items")
    if not items:
        continue
    n = items[0]
    print("tenderId:", n.get("tenderId"), "| procedureResult:", n.get("procedureResult"),
          "| tenderType:", n.get("tenderType"), "| contractors:", json.dumps(n.get("contractors"), ensure_ascii=False)[:500])
    text = " ".join(TAG.sub("\n", n.get("htmlBody") or "").split())
    for kw in ["Wartość", "wartość", "Liczba otrzymanych", "ofert", "Cena", "cena", "Kryter", "kryter",
               "Okres realizacji", "Tryb", "wadium", "Wadium"]:
        for m in list(re.finditer(kw, text))[:3]:
            print(f"  [{kw}] ...{text[max(0, m.start()-60):m.start()+220]}...")
