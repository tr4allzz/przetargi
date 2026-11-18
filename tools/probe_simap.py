"""Diagnostic: simap.ch detail structure (flattened key paths) for an award and an open tender."""
import json
import time

import requests

H = {"User-Agent": "przetargi-probe/0.1", "Accept": "application/json"}
S = "https://www.simap.ch/rest/publications/v2/project/project-search"
D = "https://www.simap.ch/rest/publications/v1/project/{pid}/publication-details/{pub}"
langs = [("lang", x) for x in ("de", "fr", "it", "en")]


def flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flat(v, f"{p}.{k}" if p else k)
    elif isinstance(o, list):
        if o:
            yield from flat(o[0], p + "[0]")
        else:
            yield p + "[]", "[]"
    else:
        yield p, o


r = requests.get(S, params=[("search", "Software"), *langs], headers=H, timeout=60).json()
by_type = {}
for it in r["projects"]:
    by_type.setdefault(it["pubType"], it)
print("pubTypes seen:", list(by_type))
# also new-style filter params: try to find open tenders
for extra in ([("newestPubTypes", "tender")], [("pubTypes", "tender")]):
    time.sleep(1)
    rr = requests.get(S, params=[("search", "Software"), *langs, *extra], headers=H, timeout=60)
    print("filter", extra, rr.status_code, [p["pubType"] for p in rr.json().get("projects", [])][:10] if rr.ok else rr.text[:200])

for t, it in by_type.items():
    time.sleep(1.5)
    d = requests.get(D.format(pid=it["id"], pub=it["publicationId"]), headers=H, timeout=60).json()
    print(f"\n===== {t}: {it['title']}")
    for k, v in flat(d):
        sv = json.dumps(v, ensure_ascii=False)
        if v in (None, "[]") or sv == "null":
            continue
        print(f"  {k} = {sv[:160]}")
