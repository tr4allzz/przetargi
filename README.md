# przetargi — GxP/CSV tender monitor

Codzienny monitoring przetargów publicznych pod kątem walidacji systemów skomputeryzowanych (CSV/CSA), GxP i powiązanych systemów (LIMS, eQMS, monitoring, MES) — dla Valready.

Działa w GitHub Actions (raz dziennie), wyniki commituje do repo, a przy nowych trafieniach otwiera Issue.

## Źródła

| Źródło | Zakres | Metoda | Status |
|---|---|---|---|
| `ted` | UE (TED, powyżej progów UE) | Oficjalne Search API v3, wyszukiwanie pełnotekstowe | stabilne |
| `oev` | Niemcy — oeffentlichevergabe.de (Bekanntmachungsservice), także poniżej progów UE | dzienne/miesięczne eksporty OCDS (CC0), filtr lokalny; liczba oferentów, wartość umowy | działa |
| `boamp` | Francja — BOAMP (DILA) | Opendatasoft API, wyszukiwanie pełnotekstowe | działa |
| `simap` | Szwajcaria (simap.ch — większość przetargów CH nie trafia do TED) | REST API strony: wyszukiwanie + szczegóły (termin, zwycięzcy, ceny, liczba ofert) | działa |
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

## Co jest w raporcie

- **Otwarte — do rozważenia:** karta dla każdego otwartego postępowania: termin, tryb, umowa ramowa, czas realizacji, wartość szacunkowa, kryteria oceny (z wagami, jeśli są), wadium, skrót warunków udziału.
- **Rozstrzygnięte — benchmark:** zamawiający, przedmiot, wartość szacunkowa, liczba ofert, najniższa–najwyższa oferta, kwota umowy, zwycięzca (kraj, wielkość firmy), kryteria, data. Ogłoszenie o zamówieniu i ogłoszenie o wyniku z BZP są łączone po `tenderId` w jeden wiersz.
- **Wnioski do wyceny:** mediana liczby ofert i odsetek postępowań z jedną ofertą, mediana relacji kwota umowy / wartość szacunkowa, udział postępowań „tylko cena”.

Źródła danych o wyniku: TED (pola eForms: BT-27, BT-710/711, BT-720, BT-759, zwycięzca) oraz treść ogłoszeń BZP (sekcje IV, VI, VIII). Baza Konkurencyjności nie udostępnia wyników przez API — tylko ogłoszenia.

## Typy postępowań

Każde trafienie dostaje typ (`monitor/scoring.py: classify`, reguły w `config.py`):

| Typ | Znaczenie | Korekta score |
|---|---|---:|
| `usługa CSV` | sama usługa walidacji/kwalifikacji/QM | +2 |
| `system + walidacja` | dostawa/wdrożenie systemu (LIMS, MES, EBR, QMS, monitoring) z walidacją — szansa na podwykonawstwo | +1 |
| `sprzęt + IQ/OQ` | dostawa aparatury z kwalifikacją producenta | −1 |
| `serwis urządzeń` | przeglądy techniczne + „walidacje” urządzeń | −1 |
| `inne` | usługi badawcze, odczynniki, walidacja metod itp. | −1,5 |

Wnioski do wyceny w raporcie liczone są tylko dla pierwszych dwóch typów.

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
