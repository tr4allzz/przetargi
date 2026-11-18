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
    assert "Otwarte (1)" in (tmp_path / "data" / "ALL.md").read_text()

    # second run: same tender is not new any more
    rc = cli.main(["--sources", "ok", "--root", str(tmp_path)])
    assert (tmp_path / "reports" / "NEW_COUNT").read_text() == "0"


def test_cli_all_sources_fail_returns_2(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "SOURCES", {"bad": fake_fail})
    assert cli.main(["--sources", "bad", "--root", str(tmp_path)]) == 2
