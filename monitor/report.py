"""Markdown reports with bid intelligence (values, offers, winners, criteria)."""
from __future__ import annotations

import re
import statistics
from datetime import date

from . import config
from .models import Tender

MERGE_FIELDS = ["estimated_value", "award_value", "lowest_offer", "highest_offer", "offers",
                "duration", "contract_date", "framework", "deposit", "conditions", "procedure", "deadline"]


def _esc(s: str, n: int = 120) -> str:
    s = (s or "").replace("|", "/").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _amount(v: str) -> float | None:
    """First amount in a '1 234 PLN / 5 678 PLN' string."""
    m = re.match(r"\s*([\d ]+)", v or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(" ", ""))
    except ValueError:
        return None


def _norm(s: str, n: int) -> str:
    return re.sub(r"[^a-z0-9ąćęłńóśźżäöüß]", "", (s or "").lower())[:n]


def _group(items: list[Tender]) -> dict[str, list[Tender]]:
    """Union notices that share a procedure id, or the same title + buyer (also across sources,
    e.g. the same German tender in TED and on oeffentlichevergabe.de)."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen: dict[str, int] = {}
    for i, t in enumerate(items):
        keys = [f"id:{t.tender_id}"] if t.tender_id else []
        if len(_norm(t.title, 60)) >= 12:
            keys.append(f"tb:{_norm(t.title, 60)}|{_norm(t.buyer, 20)}")
        for k in keys:
            if k in seen:
                parent[find(i)] = find(seen[k])
            else:
                seen[k] = i
    groups: dict[str, list[Tender]] = {}
    for i, t in enumerate(items):
        groups.setdefault(str(find(i)), []).append(t)
    return groups


def merge_cases(items: list[Tender]) -> list[dict]:
    """Group notices of one procedure into a single case (see _group)."""
    groups = _group(items)
    cases = []
    for ts in groups.values():
        # newest first: result notices carry offers/winners, older ones the notice details
        ts = sorted(ts, key=lambda t: t.published or "", reverse=True)
        main = max(ts, key=lambda t: t.score)
        c = {
            "title": main.title, "url": main.url, "buyer": main.buyer, "country": main.country,
            "source": ", ".join(sorted({t.source for t in ts})), "score": max(t.score for t in ts),
            "matched": main.matched,
            "published": min((t.published for t in ts if t.published), default=""),
            "result_published": ts[0].published if len(ts) > 1 else "",
            "links": [(t.notice_type or t.source, t.url) for t in ts if t.url],
            "winners": sorted({w for t in ts for w in t.winners}),
            "winner_info": next((t.winner_info for t in ts if t.winner_info), []),
            "criteria": next((t.criteria for t in ts if t.criteria), []),
            "kind": main.kind or next((t.kind for t in ts if t.kind), "") or config.KIND_OTHER,
        }
        for f in MERGE_FIELDS:
            c[f] = next((getattr(t, f) for t in ts if getattr(t, f)), "")
        cases.append(c)
    return cases


def _is_open(c: dict, today: str) -> bool:
    return bool(c["deadline"]) and c["deadline"][:10] >= today and not c["winners"] and not c["award_value"]


def _card(c: dict) -> str:
    lines = [f"#### {c['score']:.1f} · `{c['kind']}` · [{_esc(c['title'], 160)}]({c['url']})", ""]
    lines.append(f"- **Zamawiający:** {_esc(c['buyer'], 100)} ({c['country']}) · źródło: {c['source']} · "
                 f"publikacja {c['published']}")
    row = []
    if c["deadline"]:
        row.append(f"**Termin ofert:** {c['deadline']}")
    if c["procedure"]:
        row.append(f"**Tryb:** {_esc(c['procedure'], 90)}")
    if c["framework"]:
        row.append(f"**Umowa ramowa:** {c['framework']}")
    if c["duration"]:
        row.append(f"**Realizacja:** {c['duration']}")
    if row:
        lines.append("- " + " · ".join(row))
    if c["estimated_value"]:
        lines.append(f"- **Wartość szacunkowa:** {c['estimated_value']}")
    if c["criteria"]:
        lines.append(f"- **Kryteria oceny:** {', '.join(c['criteria'])}")
    if c["deposit"]:
        lines.append(f"- **Wadium:** {_esc(c['deposit'], 200)}")
    if c["conditions"]:
        lines.append(f"- **Warunki udziału (skrót):** {_esc(c['conditions'], 450)}")
    lines.append(f"- _Dopasowania:_ {', '.join(c['matched'])}")
    return "\n".join(lines)


BENCH_HEADER = ("| Typ | Zamawiający | Przedmiot | Szacunek | Ofert | Najniższa – najwyższa | Umowa | Zwycięzca | Kryteria | Data |\n"
                "|---|---|---|---:|---:|---|---:|---|---|---|")


def _bench_row(c: dict) -> str:
    rng = ""
    if c["lowest_offer"] or c["highest_offer"]:
        rng = f"{c['lowest_offer'] or '?'} – {c['highest_offer'] or '?'}"
    win = ", ".join(c["winners"])
    if c["winner_info"]:
        win += f" ({'; '.join(c['winner_info'])})"
    return (f"| {c['kind']} | {_esc(c['buyer'], 45)} | [{_esc(c['title'], 80)}]({c['url']}) | {c['estimated_value'] or '—'} | "
            f"{c['offers'] or '—'} | {rng or '—'} | {c['award_value'] or '—'} | {_esc(win, 70) or '—'} | "
            f"{_esc(', '.join(c['criteria']), 50) or '—'} | {c['contract_date'] or c['result_published'] or c['published']} |")


def _insights(cases: list[dict]) -> list[str]:
    offers = []
    for c in cases:
        nums = [int(x) for x in re.findall(r"\d+", c["offers"] or "")]
        if nums:
            offers.append(nums[0])
    ratios = []
    for c in cases:
        est, award = _amount(c["estimated_value"]), _amount(c["award_value"])
        if est and award and est > 0:
            ratios.append(award / est)
    price_only = sum(1 for c in cases if c["criteria"] and all(re.match(r"(?i)(cena|price|pris|preis)", x)
                                                               for x in c["criteria"]))
    with_crit = sum(1 for c in cases if c["criteria"])
    out = []
    if offers:
        single = sum(1 for o in offers if o == 1)
        out.append(f"- Liczba ofert: mediana **{statistics.median(offers):g}**, "
                   f"jedna oferta w **{single}/{len(offers)}** postępowań ({100 * single / len(offers):.0f}%).")
    if ratios:
        out.append(f"- Kwota umowy / wartość szacunkowa: mediana **{statistics.median(ratios):.2f}** "
                   f"(min {min(ratios):.2f}, max {max(ratios):.2f}, n={len(ratios)}).")
    if with_crit:
        out.append(f"- Wyłącznie cena jako kryterium: **{price_only}/{with_crit}** postępowań ze znanymi kryteriami.")
    return out


FREELANCE_DAYS = 45
OPEN_ORDER = [config.KIND_SERVICE, config.KIND_SYSTEM, config.KIND_EQUIPMENT, config.KIND_DEVICE_SERVICE,
              config.KIND_OTHER]
OPEN_LABEL = {config.KIND_SERVICE: "Usługi walidacji CSV", config.KIND_SYSTEM: "Systemy z walidacją",
              config.KIND_EQUIPMENT: "Sprzęt z IQ/OQ", config.KIND_DEVICE_SERVICE: "Serwis urządzeń",
              config.KIND_OTHER: "Inne"}


def _gig_row(c: dict) -> str:
    return (f"| {c['score']:.1f} | [{_esc(c['title'], 90)}]({c['url']}) | {_esc(c['buyer'], 40) or '—'} | "
            f"{c['country'] or '—'} | {_esc(c['procedure'], 60) or '—'} | {_esc(c['duration'], 40) or '—'} | "
            f"{c['published']} |")


GIG_HEADER = ("| Score | Zlecenie | Firma / pośrednik | Kraj | Forma · miejsce | Start · czas | Dodano |\n"
              "|---:|---|---|---|---|---|---|")


def _country_table(groups: dict[str, list[dict]]) -> list[str]:
    cols = list(groups)
    countries: dict[str, list[int]] = {}
    for i, col in enumerate(cols):
        for c in groups[col]:
            row = countries.setdefault(c["country"] or "?", [0] * len(cols))
            row[i] += 1
    if not countries:
        return []
    out = ["| Kraj | " + " | ".join(cols) + " | Razem |", "|---|" + "---:|" * (len(cols) + 1)]
    for k, row in sorted(countries.items(), key=lambda kv: -sum(kv[1])):
        out.append(f"| {k} | " + " | ".join(str(x) if x else "·" for x in row) + f" | **{sum(row)}** |")
    return out


def _collapsed(rows: list[str], header: str) -> list[str]:
    return ["<details><summary>Pokaż " + str(len(rows)) + " pozycji</summary>", "", header, *rows, "",
            "</details>", ""]


def render_full(items: list[Tender], today: date, title: str, intro: list[str] | None = None,
                stats: dict[str, str] | None = None, gig_days: int | None = FREELANCE_DAYS) -> str:
    t_iso = today.isoformat()
    cases = merge_cases(items)

    def _date(c):
        return c["contract_date"] or c["result_published"] or c["published"]

    gigs_all = [c for c in cases if c["kind"] == config.KIND_FREELANCE]
    cutoff = date.fromordinal(today.toordinal() - gig_days).isoformat() if gig_days else ""
    gigs = sorted([c for c in gigs_all if c["published"] >= cutoff], key=lambda c: (c["published"], c["score"]),
                  reverse=True)
    tenders = [c for c in cases if c["kind"] != config.KIND_FREELANCE]
    open_ = sorted([c for c in tenders if _is_open(c, t_iso)], key=lambda c: (c["deadline"], -c["score"]))
    closed = [c for c in tenders if c not in open_]
    csv_cases = sorted([c for c in closed if c["kind"] in config.CSV_KINDS], key=_date, reverse=True)
    awarded = [c for c in csv_cases if c["winners"] or c["award_value"]]
    adjacent = sorted([c for c in closed if c["kind"] in (config.KIND_EQUIPMENT, config.KIND_DEVICE_SERVICE)],
                      key=_date, reverse=True)
    rest = sorted([c for c in closed if c not in csv_cases and c not in adjacent], key=lambda c: -c["score"])

    out = [f"# {title}", ""]
    out += intro or []
    out += [f"Otwarte: **{len(open_)}** · zlecenia freelance: **{len(gigs)}** · zamknięte CSV (usługa / system + "
            f"walidacja): **{len(csv_cases)}**, z czego z wynikiem: **{len(awarded)}** · sprzęt i serwis urządzeń: "
            f"**{len(adjacent)}** · inne: **{len(rest)}**", ""]
    out += ["**Spis:** 1. Podsumowanie wg kraju · 2. Otwarte przetargi (wg typu) · 3. Zlecenia freelance · "
            "4. CSV — wyniki do wyceny · 5. Sprzęt i serwis · 6. Inne · 7. Status źródeł", ""]

    out += ["## 1. Podsumowanie wg kraju", ""]
    table = _country_table({"Otwarte": open_, "CSV zamknięte": csv_cases, "Sprzęt/serwis": adjacent,
                            "Inne": rest, "Freelance": gigs})
    out += (table or ["_Brak danych._"]) + [""]

    out += ["## 2. Otwarte przetargi — do rozważenia", ""]
    if open_:
        for kind in OPEN_ORDER:
            sub = [c for c in open_ if c["kind"] == kind]
            if sub:
                out += [f"### {OPEN_LABEL[kind]} ({len(sub)})", "", "\n\n".join(_card(c) for c in sub), ""]
    else:
        out += ["_Brak otwartych._", ""]

    span = f" z ostatnich {gig_days} dni" if gig_days else ""
    out += [f"## 3. Zlecenia freelance / kontrakty{span}", "",
            "_Ogłoszenia z portali freelance (nie przetargi publiczne): zwykle pośrednik, stawka do negocjacji, "
            "brak terminu składania — liczy się szybka odpowiedź._", ""]
    out += [GIG_HEADER, *(_gig_row(c) for c in gigs), ""] if gigs else ["_Brak._", ""]

    out += ["## 4. CSV: usługi walidacji i systemy z walidacją (zamknięte)", "",
            "_Jedyna część przydatna do wyceny usług CSV. W „system + walidacja” kwota obejmuje cały system; "
            "walidację zwykle robi dostawca/integrator — szansa na podwykonawstwo._", ""]
    if csv_cases:
        ins = _insights(awarded)
        if ins:
            out += [f"**Wnioski do wyceny** (n={len(awarded)} z wynikiem):", *ins, ""]
        out += [BENCH_HEADER, *(_bench_row(c) for c in csv_cases), ""]
    else:
        out += ["_Brak._", ""]

    out += ["## 5. Sprzęt z IQ/OQ i serwis urządzeń (zamknięte)", "",
            "_Kwalifikację robi producent/serwis na własnych protokołach; kwoty to głównie cena sprzętu — "
            "nie używać do wyceny CSV._", ""]
    out += _collapsed([_bench_row(c) for c in adjacent], BENCH_HEADER) if adjacent else ["_Brak._", ""]

    out += ["## 6. Inne / prawdopodobny szum", ""]
    out += _collapsed([_bench_row(c) for c in rest], BENCH_HEADER) if rest else ["_Brak._", ""]
    if stats:
        out += ["## 7. Status źródeł (ostatni przebieg)", "", *[f"- **{k}**: {v}" for k, v in stats.items()], ""]
    return "\n".join(out)


def render(new_today: list[Tender], run_new: int, stats: dict[str, str], today: date, days_back: int) -> str:
    """Daily report: everything first seen today (across all of today's runs)."""
    intro = [f"Nowe dziś (wszystkie przebiegi): **{len(new_today)}**, w tym z ostatniego przebiegu: **{run_new}** "
             f"(okno {days_back} dni).", ""]
    return render_full(new_today, today, f"Przetargi GxP/CSV — {today.isoformat()}", intro, stats, gig_days=None)


def render_all(items: list[dict]) -> str:
    ts = [Tender.from_dict(d) for d in items]
    return render_full(ts, date.today(), "Wszystkie trafienia — baza")
