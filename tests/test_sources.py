"""Parsing tests for source payload shapes (offline, no network)."""
from datetime import date

from monitor.sources import ocds, ted, ezamowienia


TED_NOTICE = {
    "publication-number": "123456-2026",
    "notice-title": {"eng": "Validation of computerised systems (GAMP 5)", "pol": "Walidacja"},
    "buyer-name": {"pol": ["Szpital Kliniczny"]},
    "buyer-country": ["POL"],
    "publication-date": "2026-11-13+01:00",
    "deadline-receipt-tender-date-lot": ["2026-12-14+01:00"],
    "classification-cpv": ["72225000", "72000000"],
    "notice-type": "cn-standard",
    "links": {"html": {"ENG": "https://ted.europa.eu/en/notice/-/detail/123456-2026"}},
}


def test_ted_to_tender():
    t = ted.to_tender(TED_NOTICE)
    assert t.key == "ted:123456-2026"
    assert t.title.startswith("Validation")
    assert t.buyer == "Szpital Kliniczny"
    assert t.published == "2026-11-13"
    assert t.deadline == "2026-12-14"
    assert "72225000" in t.cpv
    assert t.url.endswith("123456-2026")


def test_ted_query():
    assert ted.build_query("GAMP", date(2026, 11, 1)) == 'FT~"GAMP" AND publication-date>=20261101'


FTS_RELEASE = {
    "id": "080216-2025",
    "ocid": "ocds-h6vhtk-05abcd",
    "date": "2025-12-05T14:16:00Z",
    "tag": ["award"],
    "buyer": {"name": "NHS Wales Shared Services Partnership"},
    "tender": {
        "title": "EPQMS Pharmaceutical Quality Management System",
        "description": "GMP Annex 11 validation",
        "items": [{"classification": {"id": "48000000"}}],
        "tenderPeriod": {"endDate": "2025-12-20T12:00:00Z"},
    },
    "awards": [{"suppliers": [{"name": "Bizzmine UK Limited"}],
                "value": {"amount": 94080, "currency": "GBP"}}],
}


def test_ocds_release_to_tender():
    t = ocds.release_to_tender(FTS_RELEASE, "fts", "https://www.find-tender.service.gov.uk/Notice/")
    assert t.key == "fts:080216-2025"
    assert t.winners == ["Bizzmine UK Limited"]
    assert t.value == "94080 GBP"
    assert t.cpv == ["48000000"]
    assert t.url.endswith("/Notice/080216-2025")


def test_ezamowienia_defensive_mapping():
    n = {"bzpNumber": "2026/BZP 00096268", "objectId": "abc",
         "orderObject": "Dostawa wraz z walidacją systemu", "organizationName": "IITD PAN",
         "publicationDate": "2026-02-05T08:55:00", "cpvCode": "38430000-8 (Aparatura...), 72225000-8",
         "htmlBody": "<p>walidacja zgodnie z <b>GAMP 5</b></p>", "submittingOffersDate": "2026-02-17T12:00:00"}
    t = ezamowienia.to_tender(n)
    assert t.source_id == "2026/BZP 00096268"
    assert t.cpv == ["38430000", "72225000"]
    assert "GAMP 5" in t.description
    assert t.published == "2026-02-05"


def test_ezamowienia_follows_search_after_cursor(monkeypatch):
    pages = {None: [{"bzpNumber": f"a{i}", "objectId": f"o{i}"} for i in range(ezamowienia.PAGE_SIZE)],
             f"o{ezamowienia.PAGE_SIZE - 1}": [{"bzpNumber": "b1", "objectId": "x1"}]}
    seen_cursors = []

    def fake_page(self, params):
        seen_cursors.append(params.get("SearchAfter"))
        return pages[params.get("SearchAfter")]

    monkeypatch.setattr(ezamowienia._Client, "page", fake_page)
    out = {}
    n = ezamowienia._Client(None).all_pages({"NoticeType": "ContractNotice"}, out)
    assert n == ezamowienia.PAGE_SIZE + 1
    assert len(out) == ezamowienia.PAGE_SIZE + 1
    assert seen_cursors == [None, f"o{ezamowienia.PAGE_SIZE - 1}"]


def test_ezamowienia_winners():
    t = ezamowienia.to_tender({"bzpNumber": "1", "contractors": [{"contractorName": "ProGrupa"}]})
    assert t.winners == ["ProGrupa"]


def test_bk_to_tender_strips_highlights():
    from monitor.sources import bk
    t = bk.to_tender({"id": 295750, "title": ["Opracowanie, pre<mark>walidacja</mark> metody"],
                      "content": "pełna <mark>walidacja</mark> metody GMP", "advertiser_name": "Celon Pharma S.A.",
                      "publication_date": "2026-10-22", "submission_deadline": "2026-11-23 23:59:59"})
    assert t.title == "Opracowanie, prewalidacja metody"
    assert "<mark>" not in t.description
    assert t.url.endswith("/ogloszenia/295750")
    assert t.deadline == "2026-11-23 23:59"


RESULT_TEXT = ("Zamówienie udzielane jest w trybie podstawowym na podstawie: art. 275 pkt 1 ustawy SEKCJA IV "
               "4.3.) Wartość zamówienia: 200000,00 PLN 4.4.) Rodzaj zamówienia: Dostawy "
               "SEKCJA VI OFERTY 6.1.) Liczba otrzymanych ofert lub wniosków: 1 6.1.1.) Liczba otrzymanych ofert wariantowych: 0 "
               "6.2.) Cena lub koszt oferty z najniższą ceną lub kosztem: 243466,20 PLN "
               "6.3.) Cena lub koszt oferty z najwyższą ceną lub kosztem: 243466,20 PLN "
               "6.4.) Cena lub koszt oferty wykonawcy, któremu udzielono zamówienia: 243466,20 PLN "
               "SEKCJA VIII UMOWA 8.1.) Data zawarcia umowy: 2026-03-09 8.2.) Wartość umowy/umowy ramowej: 243466,20 PLN "
               "8.3.) Okres realizacji zamówienia albo umowy ramowej: 35 dni 2026-03-13")
NOTICE_TEXT = ("2.16.) Tryb udzielenia zamówienia wraz z podstawą prawną Zamówienie udzielane jest w trybie podstawowym "
               "na podstawie: art. 275 pkt 1 ustawy SEKCJA III 4.3.3.) Stosowane kryteria oceny ofert: Wyłącznie kryterium ceny "
               "Kryterium 1 4.3.5.) Nazwa kryterium: Cena 4.3.6.) Waga: 100 4.3.10.) Zamawiający określa "
               "6.4.) Zamawiający wymaga wadium: Nie 6.5.) Zamawiający wymaga zabezpieczenia")


def test_ezamowienia_parse_result_notice():
    d = ezamowienia.parse_details(RESULT_TEXT)
    assert d["estimated_value"] == "200 000 PLN"
    assert d["award_value"] == "243 466 PLN"
    assert d["lowest_offer"] == d["highest_offer"] == "243 466 PLN"
    assert d["offers"] == "1"
    assert d["contract_date"] == "2026-03-09"
    assert d["duration"].startswith("35 dni")


def test_ezamowienia_parse_contract_notice():
    d = ezamowienia.parse_details(NOTICE_TEXT)
    assert d["criteria"] == ["Cena 100"]
    assert d["deposit"] == "Nie"
    assert "art. 275 pkt 1" in d["procedure"]


def test_ted_bid_fields():
    n = dict(TED_NOTICE, **{"estimated-value-lot": ["4800000.00"], "estimated-value-cur-lot": ["DKK"],
                            "tender-value-lowest": ["2142286.00"], "tender-value-highest": ["9315420.00"],
                            "tender-value-cur": ["DKK"], "received-submissions-type-val": ["5"],
                            "received-submissions-type-code": ["tenders"], "procedure-type": "neg-w-call",
                            "award-criterion-name-lot": {"dan": ["Pris", "Solution"]},
                            "winner-country": ["GBR"], "winner-size": ["medium"],
                            "duration-period-value-lot": ["48"], "duration-period-unit-lot": ["MONTH"],
                            "framework-agreement-lot": ["fa-mix"]})
    t = ted.to_tender(n)
    assert t.estimated_value == "4 800 000 DKK"
    assert t.lowest_offer == "2 142 286 DKK" and t.highest_offer == "9 315 420 DKK"
    assert t.offers == "5"
    assert t.procedure == "negocjacyjny z ogłoszeniem"
    assert t.criteria == ["Pris", "Solution"]
    assert t.winner_info == ["GBR, medium"]
    assert t.duration == "48 month" and t.framework == "tak"


def test_ted_undisclosed_value():
    t = ted.to_tender(dict(TED_NOTICE, **{"tender-value": ["-1"], "tender-value-cur": ["EUR"]}))
    assert t.award_value == ""


def test_ted_total_value_on_contract_notice_is_not_award():
    t = ted.to_tender(dict(TED_NOTICE, **{"total-value": 375000, "estimated-value-cur-lot": ["EUR"],
                                          "estimated-value-lot": ["375000"]}))
    assert t.award_value == "" and t.estimated_value == "375 000 EUR"


def test_ted_currency_falls_back_to_estimate_and_hides_minus_one_offers():
    t = ted.to_tender(dict(TED_NOTICE, **{"winner-name": {"dan": ["Dot"]}, "total-value": 4800000,
                                          "estimated-value-cur-lot": ["DKK"],
                                          "received-submissions-type-val": ["-1", "-1"]}))
    assert t.award_value == "4 800 000 DKK"
    assert t.offers == ""


SIMAP_ITEM = {"id": "7ad8287e", "title": {"de": "Projekt «EP3» - Ersatzbeschaffung Paper Processing", "fr": None},
              "publicationId": "214a5b07", "publicationNumber": "36360-02", "publicationDate": "2026-11-18",
              "pubType": "award", "processType": "open",
              "procOfficeName": {"de": "FD - Steueramt (SST)", "fr": None}}
SIMAP_DETAIL = {
    "procurement": {"orderDescription": {"de": "<p>Lieferung mehrerer Anlagen&nbsp;GMP</p>"},
                    "cpvCode": {"code": "42991500"}, "additionalCpvCodes": [{"code": "50530000"}]},
    "decision": {"vendors": [{"vendorName": "Müller Martini AG", "vendorAddress": {"countryId": "CH"},
                              "price": {"currency": "chf", "price": 833915.0}}],
                 "numberOfSubmissions": 1, "awardDecisionDate": "2026-11-12"},
    "dates": {"offerDeadline": "2027-01-15T23:59:00+01:00"},
    "criteria": {"awardCriteriaNote": {"de": "Kriterien sind in den Dokumenten hinterlegt"}},
}


def test_simap_to_tender():
    from monitor.sources import simap
    t = simap.to_tender(SIMAP_ITEM, SIMAP_DETAIL)
    assert t.key == "simap:36360-02"
    assert t.title.startswith("Projekt «EP3»")
    assert t.description == "Lieferung mehrerer Anlagen GMP"
    assert t.cpv == ["42991500", "50530000"]
    assert t.winners == ["Müller Martini AG"] and t.winner_info == ["CH"]
    assert t.award_value == "833 915 CHF" and t.offers == "1"
    assert t.contract_date == "2026-11-12"
    assert t.deadline == "2027-01-15 23:59"
    assert t.procedure == "offen" and t.tender_id == "simap:7ad8287e"
    assert t.criteria == ["Kriterien sind in den Dokumenten hinterlegt"]


def test_simap_without_detail_keeps_search_hit():
    from monitor.sources import simap
    t = simap.to_tender(SIMAP_ITEM, None)
    assert t.source_id == "36360-02" and t.buyer == "FD - Steueramt (SST)"


OEV_REL = {
    "ocid": "ocds-mnwr74-1d0513df", "id": "f71b1b9a", "date": "2026-11-16T00:00:00+01:00", "tag": ["award"],
    "buyer": {"name": "Universitätsklinikum X"},
    "tender": {"id": "1d0513df", "title": "Validierung LIMS (GAMP 5)", "description": "GMP Labor",
               "items": [{"classification": {"id": "72000000"}}], "procurementMethodDetails": "Open procedure",
               "numberOfTenderers": 3, "tenderers": [{"name": "A GmbH"}],
               "lots": [{"title": "Los 1", "description": "Computersystemvalidierung"}]},
    "awards": [{"suppliers": [{"name": "A GmbH"}]}],
    "contracts": [{"value": {"amount": 120000, "currency": "EUR"}, "dateSigned": "2026-09-13T22:00:00.000Z"}],
}


def test_oev_to_tender():
    from monitor.sources import oev
    t = oev.to_tender(OEV_REL, "f71b1b9a", "01")
    assert t.key == "oev:f71b1b9a-01"
    assert "noticeId=f71b1b9a&noticeVersion=01" in t.url
    assert t.offers == "3" and t.award_value == "120 000 EUR" and t.contract_date == "2026-09-13"
    assert t.winners == ["A GmbH"] and "Computersystemvalidierung" in t.description
    assert t.tender_id == "oev:1d0513df"


def test_oev_periods():
    from datetime import date
    from monitor.sources import oev
    assert len(oev._periods(date(2026, 11, 16), date(2026, 11, 18))) == 3
    m = oev._periods(date(2026, 1, 5), date(2026, 11, 18))
    assert m[0] == {"pubMonth": "2026-01"} and m[-1] == {"pubMonth": "2026-11"}


def test_boamp_to_tender():
    from monitor.sources import boamp
    r = {"idweb": "26-1", "objet": "Validation des systèmes informatisés BPF", "nomacheteur": "CHU de Lyon",
         "dateparution": "2026-11-13", "datelimitereponse": "2026-12-09T12:00:00+00:00",
         "titulaire": None, "procedure_libelle": "Procédure Ouverte", "nature_libelle": "Avis de marché",
         "descripteur_libelle": ["Informatique (prestations de services)"],
         "url_avis": "https://www.boamp.fr/pages/avis/?q=idweb:26-1",
         "donnees": '{"FNSimple": {"objet": {"description": "Prestations de validation des systèmes informatisés selon GAMP 5 pour la pharmacie"}, "cpv": "72000000-5"}}'}
    t = boamp.to_tender(r)
    assert t.key == "boamp:26-1" and t.deadline == "2026-12-09 12:00"
    assert "GAMP 5" in t.description and t.cpv == ["72000000"]
