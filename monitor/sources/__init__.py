"""Source registry. Each fetcher: (session, since: date) -> list[Tender]."""
from . import bk, ezamowienia, ocds, simap, ted

SOURCES = {
    "ted": ted.fetch,
    "fts": ocds.fetch_fts,
    "contracts_finder": ocds.fetch_cf,
    "ezamowienia": ezamowienia.fetch,
    "bk": bk.fetch,
    "simap": simap.fetch,
}

# Sources without server-side keyword search scan everything in the window;
# cap their look-back so a historical backfill does not run for hours.
MAX_DAYS_BACK = {
    "ted": 3650,
    "fts": 7,
    "contracts_finder": 60,
    "ezamowienia": 365,
    "bk": 365,
    "simap": 730,
}

# Sources run by the daily schedule (FTS is too slow for daily runs; see ocds.py).
DEFAULT_SOURCES = ["ted", "simap", "contracts_finder", "ezamowienia", "bk"]
