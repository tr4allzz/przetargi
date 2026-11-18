"""Type classification on real titles from the first backfill (Nov 2026)."""
import pytest

from monitor.models import Tender
from monitor.scoring import classify

CASES = [
    ("IT- und QM-Dienstleistungen", ["72000000"], "usługa CSV"),
    ("Walidacja i utrzymanie zainstalowanego automatycznego systemu monitorującego temperaturę oraz "
     "wilgotność w lodówkach", [], "usługa CSV"),
    ("Zapytanie ofertowe nr 1/2026 dotyczące dostawy, wdrożenia i walidacji systemu LIMS wspomagającego "
     "procesy kontroli jakości", [], "system + walidacja"),
    ("Zapytanie ofertowe nr 2/2026 dotyczące dostawy, wdrożenia i walidacji systemu Electronic Batch Report "
     "(EBR) z funkcją MES", [], "system + walidacja"),
    ("Dostawa wraz z walidacją systemu służącego monitorowaniu sprzętu warunkującego wdrożenie w biobanku",
     ["38430000"], "system + walidacja"),
    ("Quality Management System", ["72000000"], "system + walidacja"),
    ("NUM RC - Pharma-Monitoring", ["45310000"], "system + walidacja"),
    ("Dostawa elektroporatora wraz z kwalifikacją IQ/OQ (produkcja) (zgodny z GMP)", ["33100000"], "sprzęt + IQ/OQ"),
    ("Automatisiertes Zellprozessierungssystem", ["33000000"], "sprzęt + IQ/OQ"),
    ("Isolator voor cytotoxische en monoclonale bereidingen", ["33190000"], "sprzęt + IQ/OQ"),
    ("1 System Erzeugung, Lagerung und Verteilung von Aqua Purificata(AP) und Water for injection(WFI)",
     ["42000000"], "sprzęt + IQ/OQ"),
    ("Zapytanie ofertowe na wynajem aparatury GC-MS na potrzeby firmy ASLAB SCIENCE", [], "sprzęt + IQ/OQ"),
    ("Закупуване на UV-Vis спектрофотометър", ["38430000"], "sprzęt + IQ/OQ"),
    ("Świadczenie usługi w zakresie przeglądów technicznych i walidacji wraz z gotowością do usuwania awarii "
     "urządzeń", [], "serwis urządzeń"),
    ("Świadczenie usług serwisu pogwarancyjnego tj. przeglądy techniczne, walidacje, diagnostyka", [], "serwis urządzeń"),
    ("High Throughput Transient Antibody Production and Characterisation Services", ["73000000"], "inne"),
    ("Belieferung von Reinraumbekleidung und -mopps", ["98310000"], "inne"),
    ("Dostawa odczynników w 2 pakietach walidacja związków nukleozydowych", ["33690000"], "inne"),
    ("Usługa: Rozwój i optymalizacja pożywki wraz z testem procesowym", [], "inne"),
    ("Closed Loop Medication Management (CLMM), Architekt mit Gesamtleitung", ["71000000"], "inne"),
    ("249 Qualifizierung und Requalifizierung Reinräume", ["71600000"], "usługa CSV"),
]


@pytest.mark.parametrize("title,cpv,expected", CASES)
def test_classify(title, cpv, expected):
    assert classify(Tender(source="t", source_id="1", title=title, cpv=cpv)) == expected
