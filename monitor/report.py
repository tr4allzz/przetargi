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


def merge_cases(items: list[Tender]) -> list[dict]:
    """Group notices of one procedure (BZP: shared tenderId) into a single case."""
    groups: dict[str, list[Tender]] = {}
    for t in items:
        groups.setdefault(t.tender_id or t.key, []).append(t)
    cases = []
    for ts in groups.values():
        # newest first: result notices carry offers/winners, older ones the notice details
        ts = sorted(ts, key=lambda t: t.published or "", reverse=True)
        main = max(ts, key=lambda t: t.score)
        c = {
            "title": main.title, "url": main.url, "buyer": main.buyer, "country": main.country,
            "source": main.source, "score": max(t.score for t in ts), "matched": main.matched,
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
    lines = [f"### {c['score']:.1f} · `{c['kind']}` · [{_esc(c['title'], 160)}]({c['url']})", ""]
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


def render_full(items: list[Tender], today: date, title: str, intro: list[str] | None = None,
                stats: dict[str, str] | None = None) -> str:
    t_iso = today.isoformat()
    cases = merge_cases(items)
    open_ = sorted([c for c in cases if _is_open(c, t_iso)], key=lambda c: (c["deadline"], -c["score"]))
    def _date(c):
        return c["contract_date"] or c["result_published"] or c["published"]

    closed = [c for c in cases if c not in open_]
    csv_cases = sorted([c for c in closed if c["kind"] in config.CSV_KINDS], key=_date, reverse=True)
    awarded = [c for c in csv_cases if c["winners"] or c["award_value"]]
    adjacent = sorted([c for c in closed if c["kind"] in (config.KIND_EQUIPMENT, config.KIND_DEVICE_SERVICE)],
                      key=_date, reverse=True)
    rest = sorted([c for c in closed if c not in csv_cases and c not in adjacent], key=lambda c: -c["score"])

    out = [f"# {title}", ""]
    out += intro or []
    out += [f"Otwarte: **{len(open_)}** · zamknięte CSV (usługa / system + walidacja): **{len(csv_cases)}**, "
            f"z czego z wynikiem: **{len(awarded)}** · sprzęt i serwis urządzeń: **{len(adjacent)}** · "
            f"inne: **{len(rest)}**", ""]
    out += ["## Otwarte — do rozważenia", ""]
    out += ["\n\n".join(_card(c) for c in open_) if open_ else "_Brak otwartych._", ""]

    out += ["## CSV: usługi walidacji i systemy z walidacją (zamknięte)", "",
            "_Jedyna część przydatna do wyceny usług CSV. W „system + walidacja” kwota obejmuje cały system; "
            "walidację zwykle robi dostawca/integrator — szansa na podwykonawstwo._", ""]
    if csv_cases:
        ins = _insights(awarded)
        if ins:
            out += [f"**Wnioski do wyceny** (n={len(awarded)} z wynikiem):", *ins, ""]
        out += [BENCH_HEADER, *(_bench_row(c) for c in csv_cases), ""]
    else:
        out += ["_Brak._", ""]

    out += ["## Sprzęt z IQ/OQ i serwis urządzeń (zamknięte)", "",
            "_Kwalifikację robi producent/serwis na własnych protokołach; kwoty to głównie cena sprzętu — "
            "nie używać do wyceny CSV._", ""]
    if adjacent:
        out += ["<details><summary>Pokaż " + str(len(adjacent)) + " pozycji</summary>", "", BENCH_HEADER,
                *(_bench_row(c) for c in adjacent), "", "</details>", ""]
    else:
        out += ["_Brak._", ""]

    out += ["## Inne / prawdopodobny szum", ""]
    if rest:
        out += ["<details><summary>Pokaż " + str(len(rest)) + " pozycji</summary>", "", BENCH_HEADER,
                *(_bench_row(c) for c in rest), "", "</details>", ""]
    else:
        out += ["_Brak._", ""]
    if stats:
        out += ["## Status źródeł (ostatni przebieg)", "", *[f"- **{k}**: {v}" for k, v in stats.items()], ""]
    return "\n".join(out)


def render(new_today: list[Tender], run_new: int, stats: dict[str, str], today: date, days_back: int) -> str:
    """Daily report: everything first seen today (across all of today's runs)."""
    intro = [f"Nowe dziś (wszystkie przebiegi): **{len(new_today)}**, w tym z ostatniego przebiegu: **{run_new}** "
             f"(okno {days_back} dni).", ""]
    return render_full(new_today, today, f"Przetargi GxP/CSV — {today.isoformat()}", intro, stats)


def render_all(items: list[dict]) -> str:
    ts = [Tender.from_dict(d) for d in items]
    return render_full(ts, date.today(), "Wszystkie trafienia — baza")
