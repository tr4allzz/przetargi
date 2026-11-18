# przetargi — GxP/CSV tender monitor

Codzienny monitoring przetargów publicznych pod kątem walidacji systemów skomputeryzowanych (CSV/CSA), GxP i powiązanych systemów (LIMS, eQMS, monitoring, MES) — dla Valready.

Działa w GitHub Actions (raz dziennie), wyniki commituje do repo, a przy nowych trafieniach otwiera Issue.

## Źródła

| Źródło | Zakres | Metoda | Status |
|---|---|---|---|
| `ted` | UE (TED, powyżej progów UE) | Oficjalne Search API v3, wyszukiwanie pełnotekstowe | stabilne |
| `fts` | UK Find a Tender | OCDS API, skan wszystkiego z okna + filtr lokalny | stabilne |
| `contracts_finder` | UK poniżej progów | OCDS API, skan + filtr | stabilne |
| `ezamowienia` | PL, BZP (ogłoszenia + wyniki) | API tablicy e-Zamówień, skan + filtr | do weryfikacji w 1. przebiegu |
| `bk` | PL, Baza Konkurencyjności | nieudokumentowane API | eksperymentalne |

Każde źródło jest izolowane — awaria jednego nie zatrzymuje reszty; status jest w raporcie.

## Wyniki

- `reports/latest.md` — nowe trafienia z ostatniego przebiegu (+ status źródeł)
- `reports/YYYY-MM-DD.md` — archiwum dzienne
- `data/ALL.md` — wszystkie trafienia: otwarte i zamknięte (z wygranymi, jeśli są)
- `data/tenders.json` — baza (klucz `źródło:id`, `first_seen`, score, dopasowania)

## Score (0–10)

Patrz `monitor/config.py`. Trafienie wymaga terminu walidacyjnego **i** (silnego terminu CSV albo kontekstu GxP/farmacja/krew/biobank/aseptyka). Bonus za CPV 72225000, kary za fałszywe trafienia (walidacja modeli ML, egzaminy zawodowe). Próg domyślny: 3.

## Uruchomienie

```bash
pip install -r requirements.txt
python -m pytest -q
python -m monitor --days-back 7                       # wszystkie źródła
python -m monitor --days-back 365 --sources ted       # backfill historyczny TED
```

Ręcznie w Actions: *Actions → Tender monitor → Run workflow* (pola: `days_back`, `sources`, `min_score`).

Limity okna dla źródeł bez wyszukiwania po słowach: FTS/Contracts Finder 60 dni, e-Zamówienia/BK 365 dni (`monitor/sources/__init__.py`).

## Planowane

- freelancermap.de / Useme / Jobgether (zlecenia CSV) — po sprawdzeniu regulaminów
- simap.ch, evergabe-online.de, service.bund.de
- zapytania ofertowe z BIP 21 RCKiK
