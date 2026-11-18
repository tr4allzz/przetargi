"""Source registry. Each fetcher: (session, since: date) -> list[Tender]."""
from . import bk, ezamowienia, ocds, ted

SOURCES = {
    "ted": ted.fetch,
    "fts": ocds.fetch_fts,
    "contracts_finder": ocds.fetch_cf,
    "ezamowienia": ezamowienia.fetch,
    "bk": bk.fetch,
}

# Sources without server-side keyword search scan everything in the window;
# cap their look-back so a historical backfill does not run for hours.
MAX_DAYS_BACK = {
    "ted": 3650,
    "fts": 60,
    "contracts_finder": 60,
    "ezamowienia": 365,
    "bk": 365,
}
