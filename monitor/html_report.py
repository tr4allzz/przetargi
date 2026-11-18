"""Self-contained interactive HTML report (tabs, filters, expandable rows). No external assets."""
from __future__ import annotations

import html
import json
from datetime import date

from . import report
from .models import Tender

TABS = [  # (section key, hash id, label)
    ("open", "otwarte", "Otwarte przetargi"),
    ("gigs", "freelance", "Zlecenia freelance"),
    ("awarded", "wyniki", "Wyniki CSV"),
    ("pending", "bez-wyniku", "CSV bez wyniku"),
    ("adjacent", "sprzet", "Sprzęt i serwis"),
    ("rest", "inne", "Inne"),
]
FIELDS = ["title", "url", "buyer", "kind", "score", "published", "deadline", "estimated_value", "award_value",
          "lowest_offer", "highest_offer", "offers", "winners", "winner_info", "criteria", "procedure", "duration",
          "framework", "deposit", "conditions", "contract_date", "result_published", "matched", "source", "links"]


def _row(c: dict, first_seen: dict[str, str]) -> dict:
    d = {k: c.get(k) for k in FIELDS}
    d["country"] = report._cc(c["country"])
    d["first_seen"] = max((first_seen.get(k, "") for k in c.get("keys", [])), default="")
    d["date"] = report._date_of(c)
    return d


def build(items: list[dict], today: date, title: str, stats: dict[str, str] | None = None,
          gig_days: int | None = report.FREELANCE_DAYS) -> str:
    first_seen = {d.get("key") or f"{d['source']}:{d['source_id']}": d.get("first_seen", "") for d in items}
    cases = report.merge_cases([Tender.from_dict(d) for d in items])
    sec = report.sections(cases, today, gig_days)
    data = {
        "today": today.isoformat(),
        "week": sec["week"],
        "recent": date.fromordinal(today.toordinal() - 2).isoformat(),
        "gigGood": report.GIG_GOOD,
        "tabs": [{"key": k, "id": i, "label": lab, "rows": [_row(c, first_seen) for c in sec[k]]} for k, i, lab in TABS],
        "insights": report._insights(sec["awarded"]),
        "stats": stats or {},
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__DATA__", blob)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1b;--muted:#6b6b66;--line:#e4e4df;--accent:#1f5fbf;--accent-bg:#e8f0fc;
--red:#b42318;--red-bg:#fdecea;--amber:#9a6700;--amber-bg:#fff4d6;--green:#1a7f37;--green-bg:#e6f4ea;}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1e;--fg:#ececea;--muted:#9b9b95;--line:#33332f;
--accent:#7aa7ff;--accent-bg:#1e2a40;--red:#ff8a80;--red-bg:#3a1f1d;--amber:#f0c060;--amber-bg:#3a3020;--green:#7ee2a0;--green-bg:#1c3324;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:16px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;cursor:pointer}
.kpi:hover{border-color:var(--accent)}
.kpi b{display:block;font-size:26px;line-height:1.1}
.kpi span{color:var(--muted);font-size:12.5px}
.tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin-top:8px}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:9px 12px;color:var(--muted);font:inherit;cursor:pointer}
.tab.on{color:var(--fg);border-bottom-color:var(--accent);font-weight:600}
.tab .n{display:inline-block;min-width:20px;padding:0 6px;margin-left:4px;border-radius:9px;background:var(--line);font-size:12px;text-align:center}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:14px 0}
.bar input[type=search]{flex:1;min-width:200px}
input,select{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:7px 10px}
label.ck{display:flex;gap:6px;align-items:center;color:var(--muted)}
.note{color:var(--muted);font-size:13px;margin:0 0 10px}
.ins{background:var(--accent-bg);border-radius:10px;padding:10px 14px;margin-bottom:12px}
.ins div{margin:2px 0}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;background:var(--bg);cursor:pointer;user-select:none;white-space:nowrap}
tr.r{cursor:pointer}tr.r:hover td{background:var(--accent-bg)}
td.num,th.num{text-align:right;white-space:nowrap}
.clamp{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
td.t{min-width:240px}
td.t a{color:var(--fg);font-weight:500;text-decoration:none}td.t a:hover{color:var(--accent);text-decoration:underline}
.muted{color:var(--muted)}
.pill{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11.5px;background:var(--line);white-space:nowrap}
.new{background:var(--green-bg);color:var(--green);font-weight:600}
.dl-red{background:var(--red-bg);color:var(--red);font-weight:600}
.dl-amber{background:var(--amber-bg);color:var(--amber);font-weight:600}
.sc{font-variant-numeric:tabular-nums;font-weight:600}
tr.det td{background:var(--bg);font-size:13px}
.det dl{display:grid;grid-template-columns:170px 1fr;gap:4px 12px;margin:4px 0}
.det dt{color:var(--muted)}.det dd{margin:0}
.cards{display:grid;gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card h3{margin:0 0 6px;font-size:16px}.card h3 a{color:var(--fg);text-decoration:none}.card h3 a:hover{color:var(--accent)}
.empty{padding:30px;text-align:center;color:var(--muted);background:var(--card);border:1px dashed var(--line);border-radius:10px}
.foot{margin-top:28px;color:var(--muted);font-size:12.5px}
.foot li{margin:2px 0}
@media (max-width:700px){.hide-m{display:none}.det dl{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<h1>__TITLE__</h1>
<div class="sub" id="gen"></div>
<div class="kpis" id="kpis"></div>
<div class="tabs" id="tabs"></div>
<div class="bar">
  <input type="search" id="q" placeholder="Szukaj: tytuł, zamawiający, zwycięzca…">
  <select id="country"><option value="">Wszystkie kraje</option></select>
  <select id="minscore"><option value="0">Każdy score</option><option value="5">score ≥ 5</option><option value="7">score ≥ 7</option><option value="9">score ≥ 9</option></select>
  <label class="ck"><input type="checkbox" id="onlynew"> tylko nowe (ostatnie 2 dni)</label>
</div>
<div id="view"></div>
<div class="foot" id="foot"></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = iso => { const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}:\d{2}))?/.exec(iso || ''); if (!m) return iso || '';
  return `${m[3]}.${m[2]}.${m[1]}` + (m[4] && m[4] !== '00:00' ? ' ' + m[4] : ''); };
const daysLeft = iso => Math.round((new Date(iso.slice(0,10)) - new Date(D.today)) / 864e5);
const isNew = r => r.first_seen && r.first_seen >= D.recent;
const tabById = Object.fromEntries(D.tabs.map(t => [t.id, t]));
let cur = 'otwarte', sort = null, openRow = null;
const store = { get(k){ try { return localStorage.getItem('przetargi.' + k); } catch(e) { return null; } },
  set(k, v){ try { localStorage.setItem('przetargi.' + k, v); } catch(e) {} } };

const COLS = {
  otwarte: null,
  freelance: [['title','Zlecenie'],['buyer','Firma / pośrednik'],['procedure','Forma · miejsce','hide-m'],['duration','Start · czas','hide-m'],['published','Dodano'],['score','Score','num']],
  wyniki: [['date','Data'],['buyer','Zamawiający'],['title','Przedmiot'],['estimated_value','Szacunek','num hide-m'],['offers','Ofert','num'],['award_value','Umowa','num'],['winners','Zwycięzca']],
  'bez-wyniku': [['date','Data'],['kind','Typ','hide-m'],['buyer','Zamawiający'],['title','Przedmiot'],['estimated_value','Szacunek','num hide-m']],
  sprzet: [['date','Data'],['kind','Typ','hide-m'],['buyer','Zamawiający'],['title','Przedmiot'],['award_value','Umowa','num'],['winners','Zwycięzca','hide-m']],
  inne: [['date','Data'],['kind','Typ','hide-m'],['buyer','Zamawiający'],['title','Przedmiot'],['score','Score','num']],
};
const NOTES = {
  otwarte: 'Postępowania z terminem składania ofert w przyszłości, posortowane wg terminu.',
  freelance: 'Ogłoszenia z portali freelance, nie przetargi — zwykle pośrednik, bez terminu: liczy się szybka odpowiedź.',
  wyniki: 'Zamknięte usługi CSV i systemy z walidacją z wynikiem. Przy systemach kwota obejmuje cały system.',
  'bez-wyniku': 'Termin minął, ogłoszenia o wyniku jeszcze nie ma (Baza Konkurencyjności nie publikuje wyników).',
  sprzet: 'Dostawy aparatury z kwalifikacją producenta i serwis — kwoty to cena sprzętu, nie do wyceny CSV.',
  inne: 'Trafienia słów kluczowych, które najpewniej nie są usługą CSV.',
};

function filtered(rows) {
  const q = $('#q').value.trim().toLowerCase(), cc = $('#country').value, ms = +$('#minscore').value, nw = $('#onlynew').checked;
  let out = rows.filter(r => (!cc || r.country === cc) && r.score >= ms && (!nw || isNew(r)) &&
    (!q || [r.title, r.buyer, (r.winners||[]).join(' '), r.procedure, r.kind].join(' ').toLowerCase().includes(q)));
  if (sort) { const [k, dir] = sort; out = [...out].sort((a, b) => {
    const x = a[k] ?? '', y = b[k] ?? ''; return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y), 'pl', {numeric:true})) * dir; }); }
  return out;
}

function cell(r, k) {
  if (k === 'title') return `<div class="clamp" title="${esc(r.title)}"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` +
    (isNew(r) ? ' <span class="pill new">nowe</span>' : '') + '</div>';
  if (k === 'score') return `<span class="sc">${r.score.toFixed(1)}</span>`;
  if (k === 'published' || k === 'date') return esc(fmt(r[k]));
  if (k === 'winners') return esc((r.winners || []).join(', ')) || '<span class="muted">—</span>';
  if (k === 'procedure') return esc((r.procedure || '').replace(/,? ?remote 0%/, '').replace('kontrakt (freelance)', 'kontrakt').replace('ANÜ (leasing pracownika)', 'ANÜ'));
  if (k === 'buyer') return `<div class="clamp" title="${esc(r.buyer)}">${esc(r.buyer)} <span class="muted">· ${esc(r.country)}</span></div>`;
  if (k === 'winners') return `<div class="clamp">${esc((r.winners || []).join(', ')) || '<span class="muted">—</span>'}</div>`;
  if (k === 'offers' && r.lowest_offer && r.highest_offer && r.lowest_offer !== r.highest_offer)
    return esc(r.offers) + `<div class="muted">${esc(r.lowest_offer)} – ${esc(r.highest_offer)}</div>`;
  return esc(r[k]) || '<span class="muted">—</span>';
}

function details(r) {
  const f = [['Typ', r.kind], ['Źródło', r.source], ['Publikacja', fmt(r.published)], ['Termin ofert', fmt(r.deadline)],
    ['Wartość szacunkowa', r.estimated_value], ['Kwota umowy', r.award_value], ['Liczba ofert', r.offers],
    ['Najniższa – najwyższa', r.lowest_offer || r.highest_offer ? `${r.lowest_offer || '?'} – ${r.highest_offer || '?'}` : ''],
    ['Zwycięzca', [(r.winners || []).join(', '), (r.winner_info || []).join('; ')].filter(Boolean).join(' — ')],
    ['Kryteria', (r.criteria || []).join(', ')], ['Tryb / forma', r.procedure], ['Umowa ramowa', r.framework],
    ['Realizacja / czas', r.duration], ['Data umowy', fmt(r.contract_date)], ['Wadium', r.deposit],
    ['Warunki udziału', r.conditions], ['Dopasowania', (r.matched || []).join(', ')], ['Score', r.score.toFixed(1)]];
  const links = (r.links || []).map(([n, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)}</a>`).join(' · ');
  return `<dl>${f.filter(x => x[1]).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}` +
    (links ? `<dt>Ogłoszenia</dt><dd>${links}</dd>` : '') + '</dl>';
}

function deadlinePill(r) {
  const n = daysLeft(r.deadline), cls = n <= 7 ? 'dl-red' : n <= 21 ? 'dl-amber' : '';
  const txt = n === 0 ? 'dziś' : n === 1 ? 'jutro' : `za ${n} dni`;
  return `<span class="pill ${cls}">termin ${esc(fmt(r.deadline))} · ${txt}</span>`;
}

function renderOpen(rows) {
  if (!rows.length) return '<div class="empty">Brak otwartych postępowań dla tych filtrów.</div>';
  return '<div class="cards">' + rows.map(r => `<div class="card">
    <h3><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a> ${isNew(r) ? '<span class="pill new">nowe</span>' : ''}</h3>
    <div style="margin-bottom:6px"><b>${esc(r.buyer)}</b> <span class="muted">· ${esc(r.country)}</span> &nbsp; ${deadlinePill(r)}
      <span class="pill">${esc(r.kind)}</span> <span class="pill sc">score ${r.score.toFixed(1)}</span></div>
    <div class="det">${details(r)}</div></div>`).join('') + '</div>';
}

function renderTable(id, rows) {
  if (!rows.length) return '<div class="empty">Brak pozycji dla tych filtrów.</div>';
  const cols = COLS[id];
  const head = cols.map(([k, l, c]) => `<th class="${c || ''}" data-k="${k}">${l}${sort && sort[0] === k ? (sort[1] > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('');
  const body = rows.map((r, i) => {
    const key = id + ':' + i + ':' + r.url;
    const tr = `<tr class="r" data-key="${esc(key)}">` + cols.map(([k, , c]) =>
      `<td class="${(c || '') + (k === 'title' ? ' t' : '')}">${cell(r, k)}</td>`).join('') + '</tr>';
    return tr + (openRow === key ? `<tr class="det"><td colspan="${cols.length}">${details(r)}</td></tr>` : '');
  }).join('');
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function render() {
  const t = tabById[cur], rows = filtered(t.rows);
  $('#tabs').innerHTML = D.tabs.map(x => `<button class="tab ${x.id === cur ? 'on' : ''}" data-id="${x.id}">${x.label}<span class="n">${filtered(x.rows).length}</span></button>`).join('');
  let h = `<p class="note">${NOTES[cur]}</p>`;
  if (cur === 'wyniki' && D.insights.length)
    h += '<div class="ins"><b>Wnioski do wyceny</b>' + D.insights.map(s => `<div>${esc(s.replace(/^- /, '')).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')}</div>`).join('') + '</div>';
  if (cur === 'freelance') {
    const good = rows.filter(r => r.score >= D.gigGood), weak = rows.filter(r => r.score < D.gigGood);
    h += `<h3 style="font-size:15px">Trafne (${good.length})</h3>` + renderTable(cur, good);
    if (weak.length) h += `<details style="margin-top:14px"><summary class="muted">Słabiej dopasowane (${weak.length})</summary><div style="margin-top:8px">${renderTable(cur, weak)}</div></details>`;
  } else h += cur === 'otwarte' ? renderOpen(rows) : renderTable(cur, rows);
  $('#view').innerHTML = h;
}

function kpis() {
  const T = k => D.tabs.find(t => t.key === k).rows;
  const op = T('open'), gg = T('gigs').filter(r => r.score >= D.gigGood);
  const next = op[0] ? `najbliższy: ${fmt(op[0].deadline)} · ${op[0].buyer}` : 'brak';
  const items = [['otwarte', op.length, 'otwarte przetargi', next],
    ['freelance', gg.length, 'trafne zlecenia freelance', `z ostatnich 7 dni: ${gg.filter(r => r.published >= D.week).length}`],
    ['wyniki', T('awarded').length, 'wyniki CSV do wyceny', `czeka na wynik: ${T('pending').length}`],
    ['sprzet', T('adjacent').length + T('rest').length, 'sprzęt, serwis i inne', 'zwykle nie dla CSV']];
  $('#kpis').innerHTML = items.map(([id, n, l, s]) => `<div class="kpi" data-id="${id}"><b>${n}</b><span>${l}</span><div class="sub">${esc(s)}</div></div>`).join('');
}

function init() {
  $('#gen').textContent = `Stan na ${fmt(D.today)} · dane z TED, oeffentlichevergabe.de, simap.ch, BOAMP, e-Zamówień, Bazy Konkurencyjności, Contracts Finder i freelancermap`;
  const cs = [...new Set(D.tabs.flatMap(t => t.rows.map(r => r.country)))].sort();
  $('#country').insertAdjacentHTML('beforeend', cs.map(c => `<option>${esc(c)}</option>`).join(''));
  const st = Object.entries(D.stats);
  $('#foot').innerHTML = st.length ? '<b>Status źródeł (ostatni przebieg)</b><ul>' + st.map(([k, v]) => `<li><b>${esc(k)}</b>: ${esc(v)}</li>`).join('') + '</ul>' : '';
  ['q', 'country', 'minscore', 'onlynew'].forEach(id => { const el = $('#' + id), v = store.get(id);
    if (v !== null && id !== 'q') { if (el.type === 'checkbox') el.checked = v === '1'; else el.value = v; }
    el.addEventListener('input', () => { store.set(id, el.type === 'checkbox' ? (el.checked ? '1' : '0') : el.value); openRow = null; render(); }); });
  document.addEventListener('click', e => {
    const tab = e.target.closest('.tab, .kpi'); if (tab) { location.hash = tab.dataset.id; return; }
    const th = e.target.closest('th[data-k]'); if (th) { const k = th.dataset.k; sort = sort && sort[0] === k ? (sort[1] > 0 ? [k, -1] : null) : [k, 1]; render(); return; }
    if (e.target.closest('a')) return;
    const tr = e.target.closest('tr.r'); if (tr) { openRow = openRow === tr.dataset.key ? null : tr.dataset.key; render(); }
  });
  const route = () => { const h = location.hash.slice(1); cur = tabById[h] ? h : 'otwarte'; sort = null; openRow = null; render(); };
  window.addEventListener('hashchange', route);
  kpis(); route();
}
init();
</script>
</body>
</html>
"""
