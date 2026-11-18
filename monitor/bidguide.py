"""'Jak startować' — bidding patterns mined from closed procedures (offers, prices, criteria, winners)."""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from . import config

PRICE_RX = re.compile(r"(?i)^(cena|price|preis|pris|prix|koszt|cost)")
CUR_RX = re.compile(r"\b(PLN|EUR|CHF|DKK|NOK|SEK|GBP|CZK|MKD|USD)\b")
COND_KEYS = [  # (label, regex) — what buyers ask for in 'warunki udziału'
    ("doświadczenie (wykonane usługi/dostawy)", r"doświadczeni|wykonał\w*|referenc|experience"),
    ("wykaz osób / kwalifikacje personelu", r"wykaz\w* os|osob\w* skierowan|personel|kwalifikacj\w* zawodow|staff"),
    ("ubezpieczenie OC / sytuacja finansowa", r"ubezpiecz|\boc\b|sytuacj\w* ekonomiczn|finansow|insurance|turnover|obrót"),
    ("certyfikaty / ISO / akredytacja", r"certyfika|\biso\b|akredyta|accredit"),
    ("brak warunków (tylko wykluczenie)", r"nie określa|nie stawia|brak warunk"),
]
GROUPS = [("CSV: usługa", {config.KIND_SERVICE}), ("CSV: system + walidacja", {config.KIND_SYSTEM}),
          ("Serwis urządzeń", {config.KIND_DEVICE_SERVICE}), ("Sprzęt + IQ/OQ", {config.KIND_EQUIPMENT})]


def _money(v: str) -> tuple[float, str] | None:
    m = re.match(r"\s*([\d ]+(?:[.,]\d+)?)", v or "")
    c = CUR_RX.search(v or "")
    if not m or not c:
        return None
    try:
        return float(m.group(1).replace(" ", "").replace(",", ".")), c.group(1)
    except ValueError:
        return None


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _first_int(v: str) -> int | None:
    m = re.search(r"\d+", v or "")
    return int(m.group()) if m else None


def guide(cases: list[dict]) -> dict:
    tenders = [c for c in cases if c["kind"] != config.KIND_FREELANCE]
    results = [c for c in tenders if c["winners"] or c["award_value"]]

    amounts = []
    for label, kinds in GROUPS:
        by_cur: dict[str, list[float]] = defaultdict(list)
        for c in results:
            if c["kind"] in kinds and (m := _money(c["award_value"])):
                by_cur[m[1]].append(m[0])
        for cur, xs in sorted(by_cur.items(), key=lambda kv: -len(kv[1])):
            amounts.append({"group": label, "cur": cur, "n": len(xs), "min": _fmt(min(xs)),
                            "median": _fmt(statistics.median(xs)), "max": _fmt(max(xs))})

    offers = []
    for label, kinds in GROUPS:
        xs = [n for c in results if c["kind"] in kinds and (n := _first_int(c["offers"])) is not None]
        if xs:
            offers.append({"group": label, "n": len(xs), "median": f"{statistics.median(xs):g}",
                           "single": f"{100 * sum(1 for x in xs if x == 1) / len(xs):.0f}%", "max": max(xs)})

    ratios = []
    for c in results:
        e, a = _money(c["estimated_value"]), _money(c["award_value"])
        if e and a and e[1] == a[1] and e[0] > 0:
            ratios.append(a[0] / e[0])
    ratio = ({"n": len(ratios), "median": f"{statistics.median(ratios):.2f}", "min": f"{min(ratios):.2f}",
              "max": f"{max(ratios):.2f}",
              "below": f"{100 * sum(1 for r in ratios if r < 1) / len(ratios):.0f}%"} if ratios else None)

    with_crit = [c for c in tenders if c["criteria"]]
    price_w, other = [], Counter()
    for c in with_crit:
        for cr in c["criteria"]:
            if PRICE_RX.match(cr.strip()):
                w = re.search(r"(\d{1,3})(?:[.,]\d+)?\s*%?\s*$", cr)
                if w and 0 < int(w.group(1)) <= 100:
                    price_w.append(int(w.group(1)))
            else:
                name = re.sub(r"[\d.,%\s]+$", "", cr).strip().lower()[:50]
                if name:
                    other[name] += 1
    criteria = {"n": len(with_crit),
                "price_only": sum(1 for c in with_crit if all(PRICE_RX.match(x.strip()) for x in c["criteria"])),
                "price_weights": dict(sorted(Counter(price_w).items(), reverse=True)),
                "other": other.most_common(8)}

    with_cond = [c for c in tenders if c["conditions"]]
    conditions = {"n": len(with_cond), "items": [
        (label, sum(1 for c in with_cond if re.search(rx, c["conditions"], re.I))) for label, rx in COND_KEYS]}
    deposits = [{"buyer": c["buyer"], "title": c["title"], "url": c["url"], "deposit": c["deposit"]}
                for c in tenders if c["deposit"] and not re.match(r"(?i)\s*(nie|no)\b", c["deposit"])][:12]

    win: dict[str, dict] = {}
    for c in results:
        names = {re.sub(r"^[A-Z]{2}_", "", w.strip()) for w in c["winners"]}
        for w in sorted(names):
            k = re.sub(r"\s+(sp\.? z o\.?o\.?|spółka z ograniczoną odpowiedzialnością|gmbh|ag|s\.a\.|ltd|limited)\.?$",
                       "", w.strip(), flags=re.I).strip()
            d = win.setdefault(k.lower(), {"name": k, "wins": 0, "kinds": Counter(), "countries": Counter(),
                                           "amounts": []})
            d["wins"] += 1
            d["kinds"][c["kind"]] += 1
            d["countries"][c["country"]] += 1
            if c["award_value"]:
                d["amounts"].append(c["award_value"])
    winners = sorted(win.values(), key=lambda d: (-d["wins"], d["name"]))
    winners = [{"name": d["name"], "wins": d["wins"], "kinds": ", ".join(k for k, _ in d["kinds"].most_common()),
                "countries": ", ".join(k for k, _ in d["countries"].most_common()),
                "amounts": " · ".join(d["amounts"][:3])} for d in winners]

    return {"n_results": len(results), "n_tenders": len(tenders), "amounts": amounts, "offers": offers,
            "ratio": ratio, "criteria": criteria, "conditions": conditions, "deposits": deposits,
            "winners": winners}


def tips(g: dict) -> list[str]:
    """Plain-language takeaways derived from the numbers (only when there is data for them)."""
    out = []
    csv_off = [o for o in g["offers"] if o["group"].startswith("CSV")]
    if csv_off:
        n = sum(o["n"] for o in csv_off)
        out.append(f"W postępowaniach CSV zwykle wpływa mało ofert (mediana {csv_off[0]['median']}, n={n}) — "
                   "start z poprawną ofertą ma realną szansę; śledź ogłoszenia, bo konkurencja jest nieliczna.")
    if g["ratio"]:
        r = g["ratio"]
        out.append(f"Kwota umowy to mediana {r['median']} × wartości szacunkowej (n={r['n']}, poniżej szacunku: "
                   f"{r['below']}) — wartość szacunkowa z ogłoszenia jest dobrym pułapem ceny.")
    cr = g["criteria"]
    if cr["n"]:
        out.append(f"Tylko cena: {cr['price_only']}/{cr['n']} postępowań ze znanymi kryteriami — przy pozostałych "
                   "liczą się też jakość/doświadczenie/termin, więc warto przygotować opis metodyki i CV.")
    co = dict(g["conditions"]["items"]) if g["conditions"]["n"] else {}
    if co.get("doświadczenie (wykonane usługi/dostawy)"):
        out.append("Najczęstszy warunek udziału to doświadczenie (wykonane usługi + referencje) — zbieraj "
                   "protokoły odbioru i referencje z każdego projektu walidacyjnego.")
    return out


def to_markdown(g: dict) -> list[str]:
    out = [f"<sub>Z {g['n_results']} rozstrzygniętych postępowań (wszystkie typy, poza freelance). "
           "Mała próba — traktuj jako orientację, nie cennik.</sub>", ""]
    out += [f"- {t}" for t in tips(g)] + [""]
    if g["amounts"]:
        out += ["**Kwoty umów wg typu**", "", "| Typ | Waluta | n | min | mediana | max |", "|---|---|---:|---:|---:|---:|",
                *[f"| {a['group']} | {a['cur']} | {a['n']} | {a['min']} | {a['median']} | {a['max']} |" for a in g["amounts"]], ""]
    if g["offers"]:
        out += ["**Liczba ofert**", "", "| Typ | n | mediana | 1 oferta | max |", "|---|---:|---:|---:|---:|",
                *[f"| {o['group']} | {o['n']} | {o['median']} | {o['single']} | {o['max']} |" for o in g["offers"]], ""]
    cr = g["criteria"]
    if cr["n"]:
        w = ", ".join(f"{k}% ×{v}" for k, v in cr["price_weights"].items()) or "—"
        oth = ", ".join(f"{k} ×{v}" for k, v in cr["other"]) or "—"
        out += [f"**Kryteria** (n={cr['n']}): tylko cena {cr['price_only']}/{cr['n']} · wagi ceny: {w} · "
                f"inne kryteria: {oth}", ""]
    if g["conditions"]["n"]:
        out += [f"**Warunki udziału** (n={g['conditions']['n']}): " +
                ", ".join(f"{k} {v}" for k, v in g["conditions"]["items"] if v), ""]
    if g["winners"]:
        out += ["**Kto wygrywa**", "", "| Firma | Wygrane | Typy | Kraje | Kwoty |", "|---|---:|---|---|---|",
                *[f"| {w['name'][:50]} | {w['wins']} | {w['kinds']} | {w['countries']} | {w['amounts'][:80] or '—'} |"
                  for w in g["winners"][:25]], ""]
    return out


def to_html(g: dict) -> str:
    """Same content as to_markdown, as HTML for the interactive report."""
    import html as h

    e = lambda x: h.escape(str(x))  # noqa: E731

    def table(head, rows, num=()):
        th = "".join(f'<th class="{"num" if i in num else ""}">{e(x)}</th>' for i, x in enumerate(head))
        tr = "".join("<tr>" + "".join(f'<td class="{"num" if i in num else ""}">{e(x)}</td>' for i, x in enumerate(r))
                     + "</tr>" for r in rows)
        return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"

    out = [f'<p class="note">Z {g["n_results"]} rozstrzygniętych postępowań (wszystkie typy poza freelance). '
           "Mała próba — orientacja, nie cennik.</p>"]
    t = tips(g)
    if t:
        out.append('<div class="ins"><b>Wnioski</b>' + "".join(f"<div>• {e(x)}</div>" for x in t) + "</div>")
    if g["amounts"]:
        out.append("<h3>Kwoty umów wg typu</h3>" + table(["Typ", "Waluta", "n", "min", "mediana", "max"],
                   [[a["group"], a["cur"], a["n"], a["min"], a["median"], a["max"]] for a in g["amounts"]], (2, 3, 4, 5)))
    if g["offers"]:
        out.append("<h3>Liczba ofert</h3>" + table(["Typ", "n", "mediana", "1 oferta", "max"],
                   [[o["group"], o["n"], o["median"], o["single"], o["max"]] for o in g["offers"]], (1, 2, 3, 4)))
    cr = g["criteria"]
    if cr["n"]:
        w = ", ".join(f"{k}% ×{v}" for k, v in cr["price_weights"].items()) or "—"
        oth = ", ".join(f"{k} ×{v}" for k, v in cr["other"]) or "—"
        out.append(f"<h3>Kryteria oceny</h3><p>Znane w {cr['n']} postępowaniach · tylko cena: "
                   f"<b>{cr['price_only']}/{cr['n']}</b> · wagi ceny: {e(w)}<br>Inne kryteria: {e(oth)}</p>")
    if g["conditions"]["n"]:
        out.append(f"<h3>Warunki udziału</h3><p>Znane w {g['conditions']['n']} postępowaniach: " +
                   ", ".join(f"{e(k)} <b>{v}</b>" for k, v in g["conditions"]["items"] if v) + "</p>")
    if g["deposits"]:
        out.append("<h3>Wadium</h3><ul>" + "".join(
            f'<li><a href="{e(d["url"])}" target="_blank" rel="noopener">{e(d["buyer"][:60])}</a>: {e(d["deposit"][:160])}</li>'
            for d in g["deposits"]) + "</ul>")
    if g["winners"]:
        out.append("<h3>Kto wygrywa</h3>" + table(["Firma", "Wygrane", "Typy", "Kraje", "Kwoty"],
                   [[w["name"][:60], w["wins"], w["kinds"], w["countries"], w["amounts"] or "—"] for w in g["winners"][:40]], (1,)))
    return "".join(out)
