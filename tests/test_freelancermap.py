import html
import json
from datetime import date

from monitor.models import Tender
from monitor.report import render_full
from monitor.scoring import score
from monitor.sources import freelancermap as fm

PROJECT = {
    "id": 1085300, "slug": "csv-experte-pharma", "title": "CSV Experte Pharma (m/w/d)",
    "description": "<div>Computersystemvalidierung nach GAMP 5 und Annex 11 für einen GMP-Hersteller</div>",
    "company": "Hays AG", "city": "Basel", "country": {"iso2": "CH"}, "created": "2026-11-17T10:00:00+01:00",
    "duration": 6, "beginningText": "ab sofort",
    "projectContractType": {"type": "contracting", "remoteInPercent": 80},
    "skills": [{"de": "GxP", "en": "GxP"}], "links": {"project": "/projekt/csv-experte-pharma"},
}


def _page(projects):
    blob = html.escape(json.dumps({"initialState": {"result": {"projects": projects}}}))
    return f'<script type="application/json" class="js-react-on-rails-component" data-component-name="ProjectSearch">{blob}</script>'


def test_parse_and_map():
    ps = fm.parse_page(_page([PROJECT]))
    t = fm.to_tender(ps[0])
    assert t.url == "https://www.freelancermap.de/projekt/csv-experte-pharma"
    assert t.country == "CH" and t.published == "2026-11-17" and t.buyer == "Hays AG"
    assert "remote 80%" in t.procedure and "6 mies." in t.duration
    s = score(t)
    assert s.kind == "zlecenie freelance" and s.score >= 3


def test_report_sections():
    gig = score(fm.to_tender(PROJECT))
    tender = Tender(source="ted", source_id="1", title="Walidacja systemu GAMP 5", buyer="IITD", country="POL",
                    published="2026-11-01", deadline="2026-12-01", kind="usługa CSV", score=8)
    md = render_full([gig, tender], date(2026, 11, 18), "t")
    assert "## 1. Podsumowanie wg kraju" in md and "| CH |" in md and "| POL |" in md
    assert "### Usługi walidacji CSV (1)" in md
    sec3 = md.split("## 3.")[1].split("## 4.")[0]
    assert "CSV Experte Pharma" in sec3
    assert "CSV Experte Pharma" not in md.split("## 4.")[1]
