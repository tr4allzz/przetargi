# przetargi — GxP/CSV tender monitor

Codzienny monitoring przetargów publicznych pod kątem walidacji systemów skomputeryzowanych (CSV/CSA), GxP i powiązanych systemów (LIMS, eQMS, monitoring, MES) — dla Valready.

Działa w GitHub Actions (raz dziennie), wyniki commituje do repo, a przy nowych trafieniach otwiera Issue.

## Źródła

| Źródło | Zakres | Metoda | Status |
|---|---|---|---|
| `ted` | UE (TED, powyżej progów UE) | Oficjalne Search API v3, wyszukiwanie pełnotekstowe | stabilne |
| `ezamowienia` | PL, BZP (ogłoszenia + wyniki) | API tablicy e-Zamówień: pełny skan 7 dni (kursor `SearchAfter`) + wyszukiwanie w tytułach po stronie serwera dla całego okna | działa |
| `bk` | PL, Baza Konkurencyjności | API wyszukiwarki BK (`query`, statusy PUBLISHED/CLOSED/RESOLVED) | działa |
| `contracts_finder` | UK poniżej progów | OCDS API, skan + filtr | działa, ale paginacja/okno do sprawdzenia |
| `fts` | UK Find a Tender | OCDS API, skan + filtr | bardzo wolne API (~2–3 min/stronę) — poza codziennym harmonogramem, tylko ręcznie |

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

## Diagnostyka

Workflow *Probe (diagnostics)* uruchamia skrypty z `tools/` — tak zweryfikowano nieudokumentowane API e-Zamówień i BK.

## Planowane

- freelancermap.de / Useme / Jobgether (zlecenia CSV) — po sprawdzeniu regulaminów
- simap.ch, evergabe-online.de, service.bund.de
- zapytania ofertowe z BIP 21 RCKiK
