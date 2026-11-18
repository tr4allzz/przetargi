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
| `freelancermap` | Zlecenia freelance/kontrakty (DE/AT/CH) — nie przetargi | strony słów kluczowych `/projekte/<słowo>` z osadzonym JSON (robots.txt zezwala), ~10 zapytań/dzień | działa |
| `contracts_finder` | UK poniżej progów | OCDS API, skan + filtr | działa, ale paginacja/okno do sprawdzenia |
| `fts` | UK Find a Tender | OCDS API, skan + filtr | bardzo wolne API (~2–3 min/stronę) — poza codziennym harmonogramem, tylko ręcznie |

Każde źródło jest izolowane — awaria jednego nie zatrzymuje reszty; status jest w raporcie.

## Wyniki

- `reports/latest.md` — nowe trafienia z ostatniego przebiegu (+ status źródeł)
- `reports/YYYY-MM-DD.md` — archiwum dzienne
- `data/ALL.html` — interaktywny raport (zakładki, filtry: kraj, score, nowe; wyszukiwarka; rozwijane szczegóły) — jeden plik, otwiera się offline w przeglądarce
- `data/ALL.md` — wszystkie trafienia: otwarte i zamknięte (z wygranymi, jeśli są)
- `data/tenders.json` — baza (klucz `źródło:id`, `first_seen`, score, dopasowania)

## Co jest w raporcie

Sekcje (w tej kolejności):

1. **Podsumowanie wg kraju** — liczba pozycji per kraj w każdej sekcji.
2. **Otwarte przetargi** — podzielone wg typu (usługi CSV, systemy z walidacją, sprzęt, serwis, inne); karta: termin, tryb, umowa ramowa, czas realizacji, wartość szacunkowa, kryteria, wadium, warunki udziału.
3. **Zlecenia freelance / kontrakty** — freelancermap (w `ALL.md` z ostatnich 45 dni): firma/pośrednik, forma (kontrakt/ANÜ), remote, start, czas.
4. **CSV — wyniki do wyceny** — zamknięte usługi CSV i systemy z walidacją: wartość szacunkowa, liczba ofert, najniższa–najwyższa, kwota umowy, zwycięzca, kryteria; plus wnioski (mediana ofert, kwota/szacunek, udział „tylko cena”).
5. **Sprzęt z IQ/OQ i serwis urządzeń** (zwinięte).
6. **Inne / szum** (zwinięte).
7. **Status źródeł.**

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
| `zlecenie freelance` | ogłoszenie z portalu freelance (osobna sekcja) | +1 |

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

## Planowane / sprawdzone

- **Austria** — przetargi powyżej progów są w TED. Krajowe „Kerndaten” są rozproszone: każdy zamawiający ma własną Kerndatenquelle (od 10.2026 w eForms), a data.gv.at ma tylko metadane. Brak jednego API, więc na razie bez osobnego źródła.
- **Czechy** — powyżej progów: TED. Open data ISVZ (`isvz.nipez.cz`) nie odpowiada z runnerów GitHub (timeout); publiczne API NEN wymaga dokumentacji, której jeszcze nie przejrzałem.
- Useme / Jobgether, evergabe-online.de, service.bund.de, zapytania ofertowe z BIP 21 RCKiK.
