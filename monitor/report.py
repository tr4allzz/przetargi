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


def _d(iso: str) -> str:
    """2026-11-23 / 2026-11-23T10:00 -> 23.11.2026 (10:00)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}))?", iso or "")
    if not m:
        return iso or ""
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" + (f" {m.group(4)}" if m.group(4) and m.group(4) != "00:00" else "")


def _days_left(iso: str, today: date) -> str:
    try:
        n = (date.fromisoformat(iso[:10]) - today).days
    except ValueError:
        return ""
    return "dziś" if n == 0 else ("jutro" if n == 1 else f"za {n} dni")


def _card(c: dict, today: date | None = None) -> str:
    left = f" (**{_days_left(c['deadline'], today)}**)" if today and c["deadline"] else ""
    lines = [f"#### [{_esc(c['title'], 120)}]({c['url']})", "",
             f"**{_esc(c['buyer'], 80)}** · {_cc(c['country'])} · termin ofert: **{_d(c['deadline'])}**{left} · "
             f"score {c['score']:.1f}", ""]
    facts = [("Wartość szacunkowa", c["estimated_value"]), ("Tryb", _esc(c["procedure"], 90)),
             ("Umowa ramowa", c["framework"]), ("Realizacja", c["duration"]),
             ("Kryteria", ", ".join(c["criteria"])), ("Wadium", _esc(c["deposit"], 160)),
             ("Warunki udziału", _esc(c["conditions"], 300))]
    lines += [f"- {k}: {v}" for k, v in facts if v]
    lines.append(f"- <sub>dopasowania: {', '.join(c['matched'])} · źródło: {c['source']} · "
                 f"publikacja {_d(c['published'])}</sub>")
    return "\n".join(lines)


RESULT_HEADER = ("| Data | Zamawiający | Przedmiot | Szacunek | Ofert (rozpiętość) | Umowa | Zwycięzca | Kryteria |\n"
                 "|---|---|---|---:|---|---:|---|---|")
BENCH_HEADER = ("| Data | Typ | Zamawiający | Przedmiot | Umowa | Zwycięzca |\n"
                "|---|---|---|---|---:|---|")


def _date_of(c: dict) -> str:
    return c["contract_date"] or c["result_published"] or c["published"]


def _result_row(c: dict) -> str:
    offers = c["offers"] or "—"
    if c["lowest_offer"] and c["highest_offer"] and c["lowest_offer"] != c["highest_offer"]:
        offers += f" ({c['lowest_offer']} – {c['highest_offer']})"
    win = ", ".join(c["winners"])
    if c["winner_info"]:
        win += f" ({'; '.join(c['winner_info'])})"
    return (f"| {_d(_date_of(c))} | {_esc(c['buyer'], 35)} | [{_esc(c['title'], 60)}]({c['url']}) | "
            f"{_esc(c['estimated_value'], 30) or '—'} | {offers} | {c['award_value'] or '—'} | {_esc(win, 45) or '—'} | "
            f"{_esc(', '.join(c['criteria']), 40) or '—'} |")


def _bench_row(c: dict) -> str:
    return (f"| {_d(_date_of(c))} | {c['kind']} | {_esc(c['buyer'], 35)} | [{_esc(c['title'], 60)}]({c['url']}) | "
            f"{c['award_value'] or '—'} | {_esc(', '.join(c['winners']), 40) or '—'} |")


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
GIG_GOOD = 7.0
OPEN_ORDER = [config.KIND_SERVICE, config.KIND_SYSTEM, config.KIND_EQUIPMENT, config.KIND_DEVICE_SERVICE,
              config.KIND_OTHER]
OPEN_LABEL = {config.KIND_SERVICE: "Usługi walidacji CSV", config.KIND_SYSTEM: "Systemy z walidacją",
              config.KIND_EQUIPMENT: "Sprzęt z IQ/OQ", config.KIND_DEVICE_SERVICE: "Serwis urządzeń",
              config.KIND_OTHER: "Inne"}
ISO3 = {"DEU": "DE", "POL": "PL", "CHE": "CH", "AUT": "AT", "FRA": "FR", "GBR": "GB", "IRL": "IE", "DNK": "DK",
        "BEL": "BE", "BGR": "BG", "CZE": "CZ", "NLD": "NL", "ITA": "IT", "ESP": "ES", "SWE": "SE", "FIN": "FI",
        "NOR": "NO", "HUN": "HU", "SVK": "SK", "SVN": "SI", "ROU": "RO", "HRV": "HR", "LTU": "LT", "LVA": "LV",
        "EST": "EE", "PRT": "PT", "GRC": "GR", "LUX": "LU", "MLT": "MT", "CYP": "CY", "UK": "GB", "MKD": "MK"}


def _cc(code: str) -> str:
    code = (code or "").strip().upper()
    return ISO3.get(code, code) or "?"


GIG_HEADER = ("| Zlecenie | Firma / pośrednik | Gdzie · forma | Start · czas | Dodano |\n"
              "|---|---|---|---|---|")


def _gig_where(proc: str) -> str:
    proc = re.sub(r",? ?remote 0%", "", proc or "")
    proc = proc.replace("kontrakt (freelance)", "kontrakt").replace("ANÜ (leasing pracownika)", "ANÜ")
    return re.sub(r"remote, (.*?),? ?100% remote", r"\g<1>, 100% remote", proc).replace("· , ", "· ").strip(" ·,")


def _gig_row(c: dict) -> str:
    return (f"| [{_esc(c['title'], 70)}]({c['url']}) | {_esc(c['buyer'], 30) or '—'} | "
            f"{_esc(_gig_where(c['procedure']), 50) or '—'} | {_esc(c['duration'], 35) or '—'} | {_d(c['published'])} |")


def _country_table(groups: dict[str, list[dict]]) -> list[str]:
    cols = list(groups)
    countries: dict[str, list[int]] = {}
    for i, col in enumerate(cols):
        for c in groups[col]:
            row = countries.setdefault(_cc(c["country"]), [0] * len(cols))
            row[i] += 1
    if not countries:
        return []
    out = ["| Kraj | " + " | ".join(cols) + " | Razem |", "|---|" + "---:|" * (len(cols) + 1)]
    for k, row in sorted(countries.items(), key=lambda kv: -sum(kv[1])):
        out.append(f"| {k} | " + " | ".join(str(x) if x else "·" for x in row) + f" | **{sum(row)}** |")
    return out


def _collapsed(summary: str, body: list[str]) -> list[str]:
    return [f"<details><summary>{summary}</summary>", "", *body, "", "</details>", ""]


def render_full(items: list[Tender], today: date, title: str, intro: list[str] | None = None,
                stats: dict[str, str] | None = None, gig_days: int | None = FREELANCE_DAYS) -> str:
    t_iso = today.isoformat()
    cases = merge_cases(items)

    cutoff = date.fromordinal(today.toordinal() - gig_days).isoformat() if gig_days else ""
    gigs = sorted([c for c in cases if c["kind"] == config.KIND_FREELANCE and c["published"] >= cutoff],
                  key=lambda c: (c["published"], c["score"]), reverse=True)
    good_gigs = [c for c in gigs if c["score"] >= GIG_GOOD]
    weak_gigs = [c for c in gigs if c["score"] < GIG_GOOD]
    week = date.fromordinal(today.toordinal() - 7).isoformat()
    tenders = [c for c in cases if c["kind"] != config.KIND_FREELANCE]
    open_ = sorted([c for c in tenders if _is_open(c, t_iso)], key=lambda c: (c["deadline"], -c["score"]))
    closed = [c for c in tenders if c not in open_]
    csv_cases = sorted([c for c in closed if c["kind"] in config.CSV_KINDS], key=_date_of, reverse=True)
    awarded = [c for c in csv_cases if c["winners"] or c["award_value"]]
    pending = [c for c in csv_cases if c not in awarded]
    adjacent = sorted([c for c in closed if c["kind"] in (config.KIND_EQUIPMENT, config.KIND_DEVICE_SERVICE)],
                      key=_date_of, reverse=True)
    rest = sorted([c for c in closed if c not in csv_cases and c not in adjacent], key=lambda c: -c["score"])

    out = [f"# {title}", ""]
    out += intro or []
    nxt = f" — najbliższy termin: **{_d(open_[0]['deadline'])}** ({_esc(open_[0]['buyer'], 40)})" if open_ else ""
    out += ["> **W skrócie**",
            f"> - Otwarte przetargi: **{len(open_)}**{nxt}",
            f"> - Trafne zlecenia freelance: **{len(good_gigs)}** (z ostatnich 7 dni: "
            f"**{sum(1 for c in good_gigs if c['published'] >= week)}**)",
            f"> - Wyniki CSV do wyceny: **{len(awarded)}** · czeka na wynik: **{len(pending)}**",
            "",
            f"<sub>Otwarte: **{len(open_)}** · zlecenia freelance: **{len(gigs)}** · zamknięte CSV: **{len(csv_cases)}**, "
            f"z czego z wynikiem: **{len(awarded)}** · sprzęt i serwis: **{len(adjacent)}** · inne: **{len(rest)}**</sub>",
            ""]

    out += ["## 1. Otwarte przetargi", ""]
    if open_:
        for kind in OPEN_ORDER:
            sub = [c for c in open_ if c["kind"] == kind]
            if sub:
                out += [f"### {OPEN_LABEL[kind]} ({len(sub)})", "", "\n\n".join(_card(c, today) for c in sub), ""]
    else:
        out += ["_Brak otwartych._", ""]

    span = f" (ostatnie {gig_days} dni)" if gig_days else ""
    out += [f"## 2. Zlecenia freelance{span}", "",
            "<sub>Ogłoszenia z portali freelance, nie przetargi: zwykle pośrednik, bez terminu — liczy się szybka "
            "odpowiedź. Najnowsze na górze.</sub>", ""]
    if good_gigs:
        out += [f"### Trafne ({len(good_gigs)})", "", GIG_HEADER, *(_gig_row(c) for c in good_gigs), ""]
    if weak_gigs:
        out += _collapsed(f"Słabiej dopasowane ({len(weak_gigs)})", [GIG_HEADER, *(_gig_row(c) for c in weak_gigs)])
    if not gigs:
        out += ["_Brak._", ""]

    out += ["## 3. Wyniki CSV — do wyceny", "",
            "<sub>Zamknięte usługi CSV i systemy z walidacją. Przy systemach kwota obejmuje cały system.</sub>", ""]
    if awarded:
        out += [*_insights(awarded), "", RESULT_HEADER, *(_result_row(c) for c in awarded), ""]
    else:
        out += ["_Brak wyników._", ""]
    if pending:
        out += _collapsed(f"Bez wyniku jeszcze ({len(pending)})",
                          [f"- {_d(_date_of(c))} · {c['kind']} · **{_esc(c['buyer'], 50)}** — "
                           f"[{_esc(c['title'], 90)}]({c['url']})" for c in pending])

    out += ["## 4. Sprzęt z IQ/OQ i serwis urządzeń", "",
            "<sub>Kwalifikację robi producent; kwoty to cena sprzętu — nie do wyceny CSV.</sub>", ""]
    out += _collapsed(f"Pokaż ({len(adjacent)})", [BENCH_HEADER, *(_bench_row(c) for c in adjacent)]) \
        if adjacent else ["_Brak._", ""]

    out += ["## 5. Inne / prawdopodobny szum", ""]
    out += _collapsed(f"Pokaż ({len(rest)})", [BENCH_HEADER, *(_bench_row(c) for c in rest)]) \
        if rest else ["_Brak._", ""]

    out += ["## 6. Kraje i źródła", ""]
    table = _country_table({"Otwarte": open_, "Freelance": gigs, "CSV": csv_cases, "Sprzęt/serwis": adjacent,
                            "Inne": rest})
    body = (table or ["_Brak danych._"]) + [""]
    if stats:
        body += ["**Status źródeł (ostatni przebieg):**", "", *[f"- **{k}**: {v}" for k, v in stats.items()]]
    out += _collapsed("Podsumowanie wg kraju i status źródeł", body)
    return "\n".join(out)


def render(new_today: list[Tender], run_new: int, stats: dict[str, str], today: date, days_back: int) -> str:
    """Daily report: everything first seen today (across all of today's runs)."""
    intro = [f"Nowe dziś (wszystkie przebiegi): **{len(new_today)}**, w tym z ostatniego przebiegu: **{run_new}** "
             f"(okno {days_back} dni).", ""]
    return render_full(new_today, today, f"Przetargi GxP/CSV — {today.isoformat()}", intro, stats, gig_days=None)


def render_all(items: list[dict]) -> str:
    ts = [Tender.from_dict(d) for d in items]
    return render_full(ts, date.today(), "Wszystkie trafienia — baza")
