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
