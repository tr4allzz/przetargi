"""Markdown reports."""
from __future__ import annotations

from datetime import date

from .models import Tender


def _row(t: Tender) -> str:
    title = (t.title or "(bez tytułu)").replace("|", "/")[:140]
    link = f"[{title}]({t.url})" if t.url else title
    buyer = (t.buyer or "").replace("|", "/")[:60]
    deadline = t.deadline or "—"
    extra = ""
    if t.winners:
        extra = " · wygrał: " + ", ".join(t.winners)[:80]
    if t.value:
        extra += f" · {t.value}"
    return (f"| {t.score:.1f} | {link}{extra} | {buyer} | {t.country} | "
            f"{t.published} | {deadline} | {t.source} | {', '.join(t.matched)[:80]} |")


HEADER = ("| Score | Tytuł | Zamawiający | Kraj | Publikacja | Termin | Źródło | Dopasowania |\n"
          "|---:|---|---|---|---|---|---|---|")


def render(new: list[Tender], stats: dict[str, str], today: date, days_back: int) -> str:
    lines = [f"# Przetargi GxP/CSV — {today.isoformat()}", "",
             f"Okno: ostatnie {days_back} dni. Nowe trafienia: **{len(new)}**.", ""]
    if new:
        lines += [HEADER] + [_row(t) for t in sorted(new, key=lambda x: -x.score)]
    else:
        lines.append("_Brak nowych trafień powyżej progu._")
    lines += ["", "## Status źródeł", ""]
    lines += [f"- **{k}**: {v}" for k, v in stats.items()]
    return "\n".join(lines) + "\n"


def render_all(items: list[dict]) -> str:
    """Full table of everything in the store (data/ALL.md)."""
    ts = [Tender(**{k: v for k, v in d.items() if k in Tender.__dataclass_fields__}) for d in items]
    open_, closed = [], []
    today = date.today().isoformat()
    for t in ts:
        (open_ if (t.deadline and t.deadline[:10] >= today) else closed).append(t)
    out = ["# Wszystkie trafienia", "", f"## Otwarte ({len(open_)})", "", HEADER]
    out += [_row(t) for t in sorted(open_, key=lambda x: -x.score)]
    out += ["", f"## Zamknięte / bez terminu ({len(closed)})", "", HEADER]
    out += [_row(t) for t in sorted(closed, key=lambda x: (x.published or ""), reverse=True)]
    return "\n".join(out) + "\n"
