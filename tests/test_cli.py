"""End-to-end CLI run with fake sources (no network)."""
import json

from monitor import __main__ as cli
from monitor.models import Tender


def fake_ok(s, since):
    return [
        Tender(source="fake", source_id="1", title="Walidacja systemu LIMS zgodnie z GAMP 5",
               buyer="Szpital", country="PL", published="2026-11-17", deadline="2099-12-01"),
        Tender(source="fake", source_id="2", title="Dostawa krzeseł biurowych"),
    ]


def fake_fail(s, since):
    raise RuntimeError("boom")


def test_cli_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "SOURCES", {"ok": fake_ok, "bad": fake_fail})
    rc = cli.main(["--sources", "ok,bad", "--root", str(tmp_path), "--days-back", "3"])
    assert rc == 0
    data = json.loads((tmp_path / "data" / "tenders.json").read_text())
    assert list(data) == ["fake:1"]
    assert (tmp_path / "reports" / "NEW_COUNT").read_text() == "1"
    latest = (tmp_path / "reports" / "latest.md").read_text()
    assert "Walidacja systemu LIMS" in latest and "BŁĄD" in latest
    assert "Otwarte: **1**" in (tmp_path / "data" / "ALL.md").read_text()

    # second run: same tender is not new any more
    rc = cli.main(["--sources", "ok", "--root", str(tmp_path)])
    assert (tmp_path / "reports" / "NEW_COUNT").read_text() == "0"


def test_cli_all_sources_fail_returns_2(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "SOURCES", {"bad": fake_fail})
    assert cli.main(["--sources", "bad", "--root", str(tmp_path)]) == 2


def test_rescore_drops_items_that_no_longer_match(tmp_path, monkeypatch):
    import json as _json
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "tenders.json").write_text(_json.dumps({
        "old:1": {"source": "old", "source_id": "1", "title": "Szkolenie GAMP - analiza mięśniowo-powięziowa",
                  "score": 4.0, "matched": ["GAMP"], "first_seen": "2026-11-01"}}))
    monkeypatch.setattr(cli, "SOURCES", {"ok": fake_ok})
    cli.main(["--sources", "ok", "--root", str(tmp_path)])
    data = _json.loads((tmp_path / "data" / "tenders.json").read_text())
    assert "old:1" not in data and "fake:1" in data


def test_report_merges_notice_and_result_into_benchmark():
    from datetime import date
    from monitor.report import render_full
    notice = Tender(source="ezamowienia", source_id="N1", tender_id="ocds-1", title="Walidacja systemu GAMP 5", kind="usługa CSV",
                    buyer="IITD", published="2026-02-05", deadline="2026-02-17", estimated_value="200 000 PLN",
                    criteria=["Cena 100"], score=7)
    result = Tender(source="ezamowienia", source_id="R1", tender_id="ocds-1", title="Walidacja systemu GAMP 5", kind="usługa CSV",
                    buyer="IITD", published="2026-03-13", winners=["ProGrupa"], award_value="243 466 PLN",
                    offers="1", lowest_offer="243 466 PLN", highest_offer="243 466 PLN", score=7)
    md = render_full([notice, result], date(2026, 11, 18), "t")
    assert "z czego z wynikiem: **1**" in md
    row = [l for l in md.splitlines() if "ProGrupa" in l][0]
    assert "200 000 PLN" in row and "243 466 PLN" in row and "Cena 100" in row
    assert "jedna oferta w **1/1**" in md
    assert "mediana **1.22**" in md


def test_same_tender_in_ted_and_oev_is_merged():
    from monitor.report import merge_cases
    a = Tender(source="ted", source_id="747344-2026", title="Automatisiertes Zellprozessierungssystem",
               buyer="Universitätsklinikum Heidelberg", winners=["Miltenyi"], score=9)
    b = Tender(source="oev", source_id="x-01", title="Automatisiertes Zellprozessierungssystem",
               buyer="Universitätsklinikum Heidelberg", offers="1", score=9.5)
    cases = merge_cases([a, b])
    assert len(cases) == 1 and cases[0]["source"] == "oev, ted" and cases[0]["offers"] == "1"


def test_html_report_is_self_contained():
    import json
    from datetime import date
    from monitor.html_report import build
    item = {"source": "ted", "source_id": "1", "key": "ted:1", "first_seen": "2026-11-18", "title": "Walidacja </script> GAMP",
            "buyer": "IITD", "country": "POL", "published": "2026-11-01", "deadline": "2026-12-01", "kind": "usługa CSV",
            "score": 8.0}
    page = build([item], date(2026, 11, 18), "t", {"ted": "ok"})
    assert page.startswith("<!DOCTYPE html>") and "http://" not in page.split("<script id")[0]
    blob = page.split('<script id="data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(blob)
    assert data["tabs"][0]["rows"][0]["country"] == "PL" and data["tabs"][0]["rows"][0]["first_seen"] == "2026-11-18"
