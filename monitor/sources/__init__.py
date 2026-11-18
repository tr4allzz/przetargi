"""Source registry. Each fetcher: (session, since: date) -> list[Tender]."""
from . import bk, boamp, ezamowienia, freelancermap, ocds, oev, simap, ted

SOURCES = {
    "ted": ted.fetch,
    "fts": ocds.fetch_fts,
    "contracts_finder": ocds.fetch_cf,
    "ezamowienia": ezamowienia.fetch,
    "bk": bk.fetch,
    "simap": simap.fetch,
    "oev": oev.fetch,
    "boamp": boamp.fetch,
    "freelancermap": freelancermap.fetch,
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
    "oev": 400,
    "boamp": 730,
    "freelancermap": 60,
}

# Sources run by the daily schedule (FTS is too slow for daily runs; see ocds.py).
DEFAULT_SOURCES = ["ted", "oev", "simap", "boamp", "contracts_finder", "ezamowienia", "bk", "freelancermap"]
