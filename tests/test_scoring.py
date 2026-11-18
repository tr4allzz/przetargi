"""Scoring tests built from real notices found during manual research (Nov 2026)."""
from monitor.config import DEFAULT_MIN_SCORE
from monitor.models import Tender
from monitor.scoring import score


def s(title, description="", buyer="", cpv=None):
    return score(Tender(source="t", source_id="1", title=title, description=description,
                        buyer=buyer, cpv=cpv or []))


def test_biobank_monitoring_with_gamp_validation_is_top():
    t = s("Dostawa wraz z walidacją systemu służącego monitorowaniu sprzętu warunkującego "
          "wdrożenie w biobanku Systemu Zapewnienia Jakości",
          "system monitoringu temperatury i / lub wilgotności wraz z walidacją systemu zgodnie z GAMP 5",
          "Instytut Immunologii i Terapii Doświadczalnej")
    assert t.score >= 8, t.matched


def test_nhs_wales_epqms_is_relevant():
    t = s("EPQMS Pharmaceutical Quality Management System",
          "Pharmacy Technical Services ... must comply with Good Manufacturing Practice (GMP) "
          "and Data Integrity ... system undergoing validation to meet Annex 1 and Annex 11",
          cpv=["48000000"])
    assert t.score >= 8, t.matched


def test_csv_consultant_gig():
    t = s("Senior Computer System Validation (CSV) Consultant – GMP & IT Security")
    assert t.score >= DEFAULT_MIN_SCORE, t.matched


def test_rckik_centrifuges_with_iq_oq_surfaces():
    t = s("Dostawa, instalacja i uruchomienie 8 wirówek z osprzętem wraz z kwalifikacją "
          "instalacyjną i operacyjną", buyer="Regionalne Centrum Krwiodawstwa i Krwiolecznictwa w Poznaniu")
    assert t.score >= DEFAULT_MIN_SCORE, t.matched


def test_ml_model_validation_is_rejected():
    t = s("Zapytanie ofertowe — wybór Podwykonawcy prac badawczo-rozwojowych związanych z "
          "eksperymentalną ewaluacją i walidacją modeli machine learning",
          "automatyczne strategie inwestycyjne oparte na opcjach")
    assert t.score < DEFAULT_MIN_SCORE, t.matched


def test_exam_qualifications_rejected():
    t = s("ZOFE/ZK/14/2026 – Ułożenie zadań do egzaminu zawodowego kwalifikacja BUD.07")
    assert t.score < DEFAULT_MIN_SCORE, t.matched


def test_gmp_brand_without_validation_rejected():
    t = s("Dostawy do kopalń JSW S.A. części do kotwiarek GOPHER, Super Turbo Bolter, Merolka, GMP lub równoważne")
    assert t.score < DEFAULT_MIN_SCORE, t.matched


def test_csv_file_format_not_matched():
    t = s("Eksport danych do pliku CSV dla urzędu gminy")
    assert t.score == 0, t.matched


def test_cpv_bonus_for_system_qa():
    a = s("Validation services for GMP pharmacy software")
    b = s("Validation services for GMP pharmacy software", cpv=["72225000"])
    assert b.score > a.score


def test_contract_annex_11_alone_rejected():
    t = s("Government joint agreement for PCs", "See Annex 11 for price schedule")
    assert t.score < DEFAULT_MIN_SCORE, t.matched


def test_it_system_validation_without_gxp_context_rejected():
    t = s("Dostawa dwóch zestawów komputerowych na potrzeby projektu LIDER",
          "walidacja systemu pomiarowego w laboratorium politechniki")
    assert t.score < DEFAULT_MIN_SCORE, t.matched


def test_physio_gamp_course_rejected():
    t = s("Przygotowanie szkoleń „GAMP - GLOBALNA ANALIZA MIĘŚNIOWO-POWIĘZIOWA”")
    assert t.score < DEFAULT_MIN_SCORE, t.matched


def test_analytical_method_validation_is_not_csv():
    t = s("ZAPYTANIE OFERTOWE NR 23/2026", "Opracowanie, prewalidacja oraz pełna walidacja metody analitycznej",
          "Celon Pharma S.A.")
    assert t.score < DEFAULT_MIN_SCORE, t.matched
