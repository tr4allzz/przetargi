"""CLI: python -m monitor [--days-back N] [--sources ted,fts,...] [--min-score X]"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from .config import DEFAULT_MIN_SCORE
from .http import session
from .report import render, render_all
from .scoring import score
from .sources import MAX_DAYS_BACK, SOURCES
from .store import Store

log = logging.getLogger("monitor")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days-back", type=int, default=2)
    p.add_argument("--sources", default=",".join(SOURCES))
    p.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--fail-if-all-sources-fail", action="store_true", default=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    today = date.today()
    s = session()
    store = Store(a.root / "data" / "tenders.json")
    new, stats, failures = [], {}, 0
    names = [x.strip() for x in a.sources.split(",") if x.strip()]

    for name in names:
        fetch = SOURCES.get(name)
        if not fetch:
            stats[name] = "nieznane źródło"
            continue
        days = min(a.days_back, MAX_DAYS_BACK.get(name, a.days_back))
        since = today - timedelta(days=days)
        try:
            tenders = fetch(s, since)
        except Exception as e:  # one broken source must not kill the run
            failures += 1
            log.exception("source %s failed", name)
            stats[name] = f"BŁĄD: {type(e).__name__}: {str(e)[:200]}"
            continue
        relevant = [t for t in map(score, tenders) if t.score >= a.min_score]
        n_new = 0
        for t in relevant:
            if store.upsert(t, today):
                new.append(t)
                n_new += 1
        stats[name] = (f"ok — przeskanowano {len(tenders)}, istotnych {len(relevant)}, "
                       f"nowych {n_new} (okno {days} dni)")
        log.info("%s: %s", name, stats[name])

    store.save()
    reports = a.root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    md = render(new, stats, today, a.days_back)
    (reports / f"{today.isoformat()}.md").write_text(md, encoding="utf-8")
    (reports / "latest.md").write_text(md, encoding="utf-8")
    (a.root / "data" / "ALL.md").write_text(render_all(list(store.items.values())), encoding="utf-8")
    # marker file for the workflow: issue only when there is something new
    (reports / "NEW_COUNT").write_text(str(len(new)), encoding="utf-8")
    print(md)
    if a.fail_if_all_sources_fail and names and failures == len(names):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
