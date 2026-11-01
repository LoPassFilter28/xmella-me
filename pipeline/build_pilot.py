#!/usr/bin/env python3
"""Build the xmella.me timeline-first pilot site.

Inputs (audited sources only):
  - bundle site/data/timeline.json   (1,418 records, EN/ES summaries, provenance)
  - bundle site/data/eras.json       (10 era chapters)
  - bundle site/data/maritime_records.json + assets/maritime/*.jpg (9 clippings)
  - data/extraction*.jsonl           (our lane extractions, latest row per id)
Output: ~/workspace/chronicling-america/pilot-site/  (static, no build deps)
Design tokens: DESIGN.MD (Parchment & Ink). Typography: Segoe UI where the
device has it (Windows), with Source Sans 3 webfont as the embedded baseline
so the type renders as designed everywhere else. Browsing is paginated:
era pages of PAGE_SIZE records; the index is a directory + capped search,
never a full dump. Counts are computed from the data, never hard-coded.
"""
import json, glob, os, re, shutil, sys
from html import escape as esc

BASE = os.path.expanduser("~/workspace/chronicling-america")
BDATA = os.path.join(BASE, "handoff/bundle/site/data")
BASSETS = os.path.join(BASE, "handoff/bundle/site/assets/maritime")
OUT = os.path.join(BASE, "pilot-site")
PAGE_SIZE = 100

def load_json(p):
    d = json.load(open(p, encoding="utf-8"))
    return d if isinstance(d, list) else d.get("records", [])

timeline = load_json(os.path.join(BDATA, "timeline.json"))
eras = load_json(os.path.join(BDATA, "eras.json"))
maritime = load_json(os.path.join(BDATA, "maritime_records.json"))

# latest extraction row per id
ext = {}
for f in [os.path.join(BASE, "data/extraction.jsonl")] + sorted(glob.glob(os.path.join(BASE, "data/extraction-lane*.jsonl"))):
    if not os.path.exists(f):
        continue
    for line in open(f, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        rid, ts = r.get("id"), r.get("extracted_at", "")
        if rid and (rid not in ext or ts > ext[rid].get("extracted_at", "")):
            ext[rid] = r

timeline.sort(key=lambda r: (r["date"], r["id"]))
by_id = {r["id"]: r for r in timeline}
n_full = sum(1 for r in timeline if ext.get(r["id"], {}).get("status") == "ok" and ext[r["id"]].get("article_text"))
papers = sorted({r["newspaper"] for r in timeline})
years = (timeline[0]["date"][:4], timeline[-1]["date"][:4])
topics_all = sorted({t for r in timeline for t in (r.get("topics") or [])})
era_names = []
for r in timeline:
    if r["era"] not in era_names:
        era_names.append(r["era"])

def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

era_slug = {e: slugify(e) for e in era_names}
era_records = {e: [r for r in timeline if r["era"] == e] for e in era_names}
era_npages = {e: (len(rs) + PAGE_SIZE - 1) // PAGE_SIZE for e, rs in era_records.items()}

CSS = """
:root{--parchment:#F7F2E7;--parchment-elevated:#FCF9F1;--parchment-muted:#EDE4D0;
--ink:#1C1A17;--ink-secondary:#4C463C;--ink-muted:#7A7263;--oxblood:#7A2E2E;
--slate:#33526B;--border:#D8CCB2;--border-strong:#A08D6B}
*{box-sizing:border-box}
body{margin:0;background:var(--parchment);color:var(--ink);
font-family:"Segoe UI","Source Sans 3",-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.6}
a{color:var(--slate)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}
header.masthead{border-bottom:4px double var(--border-strong);padding:28px 20px 18px;text-align:center}
header.masthead .kicker{letter-spacing:.18em;font-size:12px;color:var(--ink-secondary);text-transform:uppercase}
header.masthead h1{margin:6px 0 4px;font-size:clamp(26px,4.5vw,42px);font-weight:700}
header.masthead .sub{color:var(--ink-secondary);font-size:15px}
.utilbar{display:flex;gap:10px;justify-content:center;align-items:center;padding:10px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.utilbar button,.utilbar a.btn{font:inherit;font-size:13px;font-weight:600;padding:5px 14px;border:1px solid var(--border-strong);
background:var(--parchment-elevated);color:var(--ink);border-radius:999px;cursor:pointer;text-decoration:none}
.utilbar button[aria-pressed="true"]{background:var(--oxblood);color:#fff;border-color:var(--oxblood)}
nav.main{display:flex;gap:18px;justify-content:center;padding:10px;font-size:14px;font-weight:600;flex-wrap:wrap}
nav.main a{color:var(--ink);text-decoration:none}
nav.main a:hover{color:var(--oxblood)}
.stats{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;margin:22px 0}
.stat{background:var(--parchment-elevated);border:1px solid var(--border);padding:10px 18px;text-align:center;min-width:130px}
.stat b{display:block;font-size:22px}
.stat span{font-size:12px;color:var(--ink-secondary);text-transform:uppercase;letter-spacing:.08em}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.controls input[type="search"],.controls select{font:inherit;font-size:14px;padding:8px 10px;border:1px solid var(--border-strong);
background:var(--parchment-elevated);color:var(--ink)}
.controls input[type="search"]{flex:1;min-width:200px}
.card{background:var(--parchment-elevated);border:1px solid var(--border);padding:16px 18px;margin:0 0 14px}
.card .meta{font-size:13px;color:var(--ink-secondary)}
.card h3{margin:4px 0 6px;font-size:18px}
.card h3 a{color:var(--ink);text-decoration:none}
.card h3 a:hover{color:var(--oxblood)}
.pills{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.pill{font-size:11px;font-weight:600;letter-spacing:.03em;border:1px solid var(--border-strong);border-radius:999px;padding:2px 9px;color:var(--ink-secondary)}
.pill.full{border-color:var(--oxblood);color:var(--oxblood)}
.hash{font-family:Consolas,"JetBrains Mono",monospace;font-size:11px;color:var(--ink-muted);word-break:break-all}
article.page{background:var(--parchment-elevated);border:1px solid var(--border);padding:26px 30px;margin-top:22px}
article.page h1{font-size:26px;margin:6px 0}
article.page .src{font-size:14px;color:var(--ink-secondary);border-bottom:1px solid var(--border);padding-bottom:12px}
article.page .body p{margin:0 0 14px;font-size:16px}
.well{background:var(--parchment-muted);border:1px solid var(--border);padding:14px 16px;margin:16px 0}
.well h4{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-secondary)}
.label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.05em;padding:2px 8px;border-radius:3px;text-transform:uppercase}
.label.doc{background:var(--slate);color:#fff}
.label.oral{background:var(--oxblood);color:#fff}
.prevnext{display:flex;justify-content:space-between;gap:12px;margin-top:22px;font-size:14px}
figure.plate{margin:18px 0;text-align:center}
figure.plate img{max-width:100%;border:1px solid var(--border-strong)}
figure.plate figcaption{font-size:13px;color:var(--ink-secondary);margin-top:6px}
footer{border-top:4px double var(--border-strong);margin-top:40px;padding:16px 20px;text-align:center;font-size:13px;color:var(--ink-secondary)}
.pager{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:center;margin:20px 0}
.pager a,.pager span.cur{font-size:13px;font-weight:600;padding:5px 12px;border:1px solid var(--border-strong);border-radius:999px;text-decoration:none;color:var(--ink);background:var(--parchment-elevated)}
.pager span.cur{background:var(--oxblood);color:#fff;border-color:var(--oxblood)}
.pager .range{width:100%;text-align:center;font-weight:400;border:none;background:none;font-size:13px;color:var(--ink-secondary)}
.morebtn{display:block;margin:6px auto 20px;font:inherit;font-size:14px;font-weight:600;padding:8px 22px;border:1px solid var(--border-strong);background:var(--parchment-elevated);color:var(--ink);border-radius:999px;cursor:pointer}
body[data-lang="en"] .l-es{display:none}
body[data-lang="es"] .l-en{display:none}
.hidden{display:none}
"""

def L(en, es):
    return f'<span class="l-en">{esc(en)}</span><span class="l-es">{esc(es)}</span>'

def head(title, depth=0):
    css = ("../" * depth) + "assets/style.css"
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | US/DR Newspaper Timeline</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css}"></head>
<body data-lang="en">
<header class="masthead"><div class="kicker">1797-1963 &middot; Library of Congress &middot; Chronicling America</div>
<h1>US/DR Newspaper Timeline</h1>
<div class="sub">{L("The Dominican Republic in the American Press: a bilingual research edition of United States newspaper coverage, 1820-1963", "La República Dominicana en la prensa estadounidense: una edición de investigación bilingüe de la cobertura periodística, 1820-1963")}</div></header>
<div class="utilbar"><span>{L("Language / Idioma", "Language / Idioma")}:</span>
<button id="btn-en" aria-pressed="true" onclick="setLang('en')">EN</button>
<button id="btn-es" aria-pressed="false" onclick="setLang('es')">ES</button></div>
<script>function setLang(l){{document.body.dataset.lang=l;document.getElementById('btn-en').setAttribute('aria-pressed',l=='en');document.getElementById('btn-es').setAttribute('aria-pressed',l=='es');localStorage.setItem('xm-lang',l);}}
(function(){{var l=localStorage.getItem('xm-lang');if(l)document.addEventListener('DOMContentLoaded',function(){{setLang(l)}});}})();</script>
"""

def nav(depth=0):
    p = "../" * depth
    return f"""<nav class="main"><a href="{p}index.html">{L("Timeline", "Cronología")}</a>
<a href="{p}eras.html">{L("Eras", "Épocas")}</a>
<a href="{p}maritime.html">{L("Mella Maritime", "Marítima Mella")}</a>
<a href="{p}method.html">{L("Method & Sources", "Método y fuentes")}</a></nav>"""

FOOT = """<footer>US/DR Newspaper Timeline &middot; xmella.me &middot;
Pilot edition. Every record links to its Library of Congress source page; provenance digests on each article page.</footer>
</body></html>"""


def paras(text):
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)

def article_page(r, prev_r, next_r):
    e = ext.get(r["id"], {})
    full = e.get("status") == "ok" and e.get("article_text")
    name = e.get("headline_as_printed") if full and e.get("headline_as_printed") else f'{r["newspaper"]} — {r["date"]}'
    h = [head(name, depth=1), nav(depth=1), '<div class="wrap"><article class="page">']
    h.append(f'<div class="meta">{esc(r["date"])} &middot; {esc(r["place"])}</div>')
    h.append(f"<h1>{esc(name)}</h1>")
    h.append(f'<div class="src">{L("Source", "Fuente")}: {esc(r["newspaper"])}, {esc(r["place"])}, {esc(r["date"])}<br>'
             f'<a href="{esc(r["source_url"])}">{esc(r["source_url"])}</a></div>')
    topics = r.get("topics") or []
    if topics:
        h.append('<div class="pills">' + "".join(f'<span class="pill">{esc(t)}</span>' for t in topics) + "</div>")
    if full:
        h.append(f'<div class="body">{paras(e["article_text"])}</div>')
        if e.get("dateline"):
            h.append(f'<div class="well"><h4>{L("Dateline as printed", "Lugar y fecha según el original")}</h4><p>{esc(e["dateline"])}</p></div>')
    else:
        h.append(f'<div class="body"><p class="l-en">{esc(r.get("summary") or "")}</p><p class="l-es">{esc(r.get("summary_es") or "")}</p></div>')
        h.append(f'<div class="well"><h4>{L("Status", "Estado")}</h4><p>{L("Full text extraction in progress; the summary above and the source page are what this pilot can stand behind today.", "Extracción del texto completo en curso; el resumen anterior y la página fuente son lo que este piloto puede respaldar hoy.")}</p></div>')
        if r.get("excerpt"):
            h.append(f'<div class="well"><h4>{L("Library of Congress OCR excerpt (locator text, not the article)", "Extracto OCR de la Biblioteca del Congreso (texto localizador, no el artículo)")}</h4><p>{esc(r["excerpt"])}</p></div>')
    prov = [f'Record: <span class="hash">{esc(r["id"])}</span>']
    if r.get("excerpt_sha256"):
        prov.append(f'Excerpt SHA-256: <span class="hash">{esc(r["excerpt_sha256"])}</span>')
    if r.get("source_text_sha256"):
        prov.append(f'Source text SHA-256: <span class="hash">{esc(r["source_text_sha256"])}</span>')
    if full:
        prov.append(f'Extraction: vision transcription, confidence {esc(str(e.get("confidence")))}, model {esc(str(e.get("model")))}, {esc(str(e.get("extracted_at"))[:10])}')
    h.append(f'<div class="well"><h4>{L("Provenance", "Procedencia")}</h4><p>{"<br>".join(prov)}</p></div>')
    h.append(f'<div class="well"><h4>{L("References", "Referencias")}</h4><p>Library of Congress, Chronicling America: '
             f'<a href="{esc(r["source_url"])}">{esc(r["newspaper"])}, {esc(r["date"])}</a>.</p></div>')
    pn = []
    if prev_r:
        pn.append(f'<a href="{esc(prev_r["id"])}.html">&larr; {esc(prev_r["date"])} {esc(prev_r["newspaper"])}</a>')
    else:
        pn.append("<span></span>")
    if next_r:
        pn.append(f'<a href="{esc(next_r["id"])}.html">{esc(next_r["date"])} {esc(next_r["newspaper"])} &rarr;</a>')
    h.append(f'<div class="prevnext">{pn[0]}{pn[1] if len(pn) > 1 else ""}</div>')
    h.append("</article></div>")
    h.append(FOOT)
    return "".join(h)

def display_name(r):
    e = ext.get(r["id"], {})
    if e.get("status") == "ok" and e.get("article_text") and e.get("headline_as_printed"):
        return e["headline_as_printed"]
    return r["newspaper"]

def is_full(r):
    e = ext.get(r["id"], {})
    return bool(e.get("status") == "ok" and e.get("article_text"))

def card(r, depth=0):
    p = "../" * depth
    topics = " ".join(r.get("topics") or [])
    pills = "".join(f'<span class="pill">{esc(t)}</span>' for t in (r.get("topics") or []))
    if is_full(r):
        pills += f'<span class="pill full">{L("Full text", "Texto completo")}</span>'
    return (f'<div class="card" data-topics="{esc(topics)}">'
            f'<div class="meta">{esc(r["date"])} &middot; {esc(r["place"])} &middot; {esc(r["era"])}</div>'
            f'<h3><a href="{p}articles/{esc(r["id"])}.html">{esc(display_name(r))}</a></h3>'
            f'<p class="l-en">{esc(r.get("summary") or "")}</p><p class="l-es">{esc(r.get("summary_es") or "")}</p>'
            f'<div class="pills">{pills}</div>'
            f'<div class="meta"><a href="{esc(r["source_url"])}">Library of Congress</a> &middot; <span class="hash">{esc(r["id"])}</span></div></div>')

def pager_html(era, k, npages, first_date, last_date, total):
    slug = era_slug[era]
    items = [f'<span class="range">{L("Records", "Registros")} {(k-1)*PAGE_SIZE+1}&ndash;{min(k*PAGE_SIZE, total)} {L("of", "de")} {total} &middot; {esc(first_date)} &ndash; {esc(last_date)}</span>']
    if k > 1:
        items.append(f'<a href="{slug}-{k-1}.html">&larr; {L("Earlier", "Anteriores")}</a>')
    for j in range(1, npages + 1):
        if j == k:
            items.append(f'<span class="cur">{j}</span>')
        else:
            items.append(f'<a href="{slug}-{j}.html">{j}</a>')
    if k < npages:
        items.append(f'<a href="{slug}-{k+1}.html">{L("Later", "Siguientes")} &rarr;</a>')
    return f'<div class="pager">{"".join(items)}</div>'

def era_pages():
    out = {}
    for era in era_names:
        rs = era_records[era]
        npages = era_npages[era]
        topic_opts = "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in topics_all)
        for k in range(1, npages + 1):
            chunk = rs[(k - 1) * PAGE_SIZE: k * PAGE_SIZE]
            h = [head(f"{era} ({k}/{npages})", depth=1), nav(depth=1), '<div class="wrap">']
            h.append(f'<div class="meta" style="margin-top:18px"><a href="../eras.html">{L("Eras", "Épocas")}</a> &middot; {L("Page", "Página")} {k} {L("of", "de")} {npages}</div>')
            h.append(f"<h2>{esc(era)}</h2>")
            h.append(f"""<div class="controls"><select id="f-topic"><option value="">{L("All topics", "Todos los temas")}</option>{topic_opts}</select></div>""")
            h.append(pager_html(era, k, npages, chunk[0]["date"], chunk[-1]["date"], len(rs)))
            h.append("".join(card(r, depth=1) for r in chunk))
            h.append(pager_html(era, k, npages, chunk[0]["date"], chunk[-1]["date"], len(rs)))
            h.append("""<script>
var ft=document.getElementById('f-topic'),cards=[].slice.call(document.querySelectorAll('.card'));
ft.addEventListener('change',function(){var t=ft.value;
cards.forEach(function(c){var ok=!t||(' '+c.dataset.topics+' ').indexOf(' '+t+' ')>-1;c.classList.toggle('hidden',!ok);});});
</script>""")
            h.append("</div>")
            h.append(FOOT)
            out[f"{era_slug[era]}-{k}.html"] = "".join(h)
    return out

def search_index():
    rows = []
    for r in timeline:
        rows.append({
            "i": r["id"], "d": r["date"], "n": r["newspaper"], "p": r["place"],
            "e": r["era"], "t": r.get("topics") or [],
            "h": display_name(r), "f": 1 if is_full(r) else 0,
            "s": (r.get("summary") or "")[:240], "x": (r.get("summary_es") or "")[:240],
        })
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

def index_page():
    h = [head("Timeline"), nav()]
    h.append('<div class="wrap">')
    h.append('<div class="stats">'
             f'<div class="stat"><b>{len(timeline)}</b><span>{L("Timeline records", "Registros")}</span></div>'
             f'<div class="stat"><b>{len(papers)}</b><span>{L("Newspapers", "Periódicos")}</span></div>'
             f'<div class="stat"><b>{years[0]}-{years[1]}</b><span>{L("Coverage", "Cobertura")}</span></div>'
             f'<div class="stat"><b>{n_full}</b><span>{L("Full texts extracted", "Textos completos")}</span></div>'
             f'<div class="stat"><b>{len(eras)}</b><span>{L("Era chapters", "Épocas")}</span></div></div>')
    h.append(f"""<div class="controls">
<input type="search" id="q" placeholder="{L("Search headlines, papers, places, summaries", "Buscar titulares, periódicos, lugares, resúmenes")}">
</div>
<div class="meta" id="count">{L("Search the full timeline, or browse by era below. Results appear 50 at a time.", "Busque en toda la cronología o explore por época. Los resultados aparecen de 50 en 50.")}</div>
<div id="results"></div>
<button class="morebtn hidden" id="more">{L("Show more results", "Mostrar más resultados")}</button>""")
    h.append(f'<h2 style="margin-top:28px">{L("Browse by era", "Explorar por época")}</h2>')
    era_meta = {e.get("era_key") or e.get("title_en"): e for e in eras}
    for era in era_names:
        rs = era_records[era]
        em = era_meta.get(era, {})
        yrs = em.get("years") or f'{rs[0]["date"][:4]}-{rs[-1]["date"][:4]}'
        h.append(f'<div class="card"><div class="meta">{esc(yrs)} &middot; {len(rs)} {L("records", "registros")} &middot; {era_npages[era]} {L("pages", "páginas")}</div>'
                 f'<h3><a href="era/{era_slug[era]}-1.html">{esc(era)}</a></h3>'
                 f'<p class="l-en">{esc(em.get("summary_en") or "")}</p><p class="l-es">{esc(em.get("summary_es") or "")}</p></div>')
    h.append("""</div>
<script>
var q=document.getElementById('q'),res=document.getElementById('results'),cnt=document.getElementById('count'),
more=document.getElementById('more'),IDX=null,matches=[],shown=0,STEP=50;
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function render(){var lang=document.body.dataset.lang||'en';
var html=matches.slice(0,shown).map(function(m){
return '<div class="card"><div class="meta">'+esc(m.d)+' &middot; '+esc(m.p)+' &middot; '+esc(m.e)+'</div>'+
'<h3><a href="articles/'+m.i+'.html">'+esc(m.h)+'</a></h3>'+
'<p>'+esc(lang=='es'?(m.x||m.s):m.s)+'</p>'+
(m.f?'<div class="pills"><span class="pill full">Full text</span></div>':'')+
'<div class="meta"><span class="hash">'+m.i+'</span></div></div>';}).join('');
res.innerHTML=html;
cnt.textContent=matches.length+' / '+IDX.length;
more.classList.toggle('hidden',shown>=matches.length);}
function run(){if(!IDX)return;var s=q.value.toLowerCase().trim();
if(!s){matches=[];shown=0;res.innerHTML='';cnt.textContent='';more.classList.add('hidden');return;}
matches=IDX.filter(function(m){return (m.d+' '+m.n+' '+m.p+' '+m.e+' '+m.h+' '+m.s+' '+m.x+' '+(m.t||[]).join(' ')).toLowerCase().indexOf(s)>-1;});
shown=Math.min(STEP,matches.length);render();}
function load(){if(IDX){run();return;}
fetch('assets/search-index.json').then(function(r){return r.json();}).then(function(j){IDX=j;run();});}
q.addEventListener('focus',load);q.addEventListener('input',function(){IDX?run():load();});
more.addEventListener('click',function(){shown=Math.min(shown+STEP,matches.length);render();});
</script>""")
    h.append(FOOT)
    return "".join(h)

def eras_page():
    counts = {}
    for r in timeline:
        counts[r["era"]] = counts.get(r["era"], 0) + 1
    h = [head("Eras"), nav(), '<div class="wrap">']
    for e in eras:
        key = e.get("era_key") or e.get("title_en")
        n = counts.get(key, 0)
        link = f'<a href="era/{era_slug[key]}-1.html">{L("Browse this era", "Ver esta época")}</a>' if n and key in era_slug else ""
        h.append(f'<div class="card"><div class="meta">{esc(e.get("years") or "")} &middot; {n} {L("records", "registros")}</div>'
                 f'<h3><span class="l-en">{esc(e.get("title_en") or "")}</span><span class="l-es">{esc(e.get("title_es") or "")}</span></h3>'
                 f'<p class="l-en">{esc(e.get("summary_en") or "")}</p><p class="l-es">{esc(e.get("summary_es") or "")}</p>{link}</div>')
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def maritime_page():
    h = [head("Mella Maritime Clippings"), nav(), '<div class="wrap">']
    h.append(f'<div class="well"><h4>{L("Evidence note", "Nota de evidencia")}</h4><p>'
             f'{L("Transcripts and scans below are documented from the clippings themselves. Research notes are reproduced from the project research files and are labeled as research notes, not as independently verified fact.", "Las transcripciones y los escaneos siguientes están documentados desde los propios recortes. Las notas de investigación se reproducen de los archivos de investigación del proyecto y se etiquetan como notas, no como hechos verificados de forma independiente.")}</p></div>')
    for m in maritime:
        img = m.get("web_image") or ""
        h.append('<article class="page" style="margin-top:14px">')
        h.append(f'<div class="meta">{esc(m.get("date") or "")} &middot; {esc(m.get("newspaper") or "")}</div>')
        h.append(f'<h1 style="font-size:22px">{esc(m.get("headline") or "")}</h1>')
        if img:
            h.append(f'<figure class="plate"><img src="assets/maritime/{esc(os.path.basename(img))}" alt="{esc(m.get("headline") or "")}">'
                     f'<figcaption>{esc(m.get("newspaper") or "")}, {esc(m.get("date") or "")} &middot; {L("Source", "Fuente")}: {esc(m.get("source_pdf") or "")}</figcaption></figure>')
        h.append(f'<p class="l-en">{esc(m.get("summary_en") or "")}</p><p class="l-es">{esc(m.get("summary_es") or "")}</p>')
        if m.get("transcript"):
            h.append(f'<div class="well"><h4>{L("Transcript", "Transcripción")}</h4>{paras(m["transcript"])}</div>')
        if m.get("research_note_en"):
            h.append(f'<div class="well"><h4><span class="label oral">{L("Research note", "Nota de investigación")}</span></h4>'
                     f'<p class="l-en">{esc(m["research_note_en"])}</p><p class="l-es">{esc(m.get("research_note_es") or "")}</p></div>')
        h.append(f'<p class="hash">SHA-256: {esc(m.get("transcript_sha256") or "")}</p>')
        h.append("</article>")
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def method_page():
    h = [head("Method & Sources"), nav(), '<div class="wrap"><article class="page">']
    h.append(f"<h1>{L('Method & Sources', 'Método y fuentes')}</h1>")
    h.append(f"""<div class="body">
<p class="l-en">This edition organizes United States newspaper coverage of the Dominican Republic from the Library of Congress Chronicling America archive. The curated timeline holds {len(timeline)} records from {len(papers)} newspapers, {years[0]} to {years[1]}, in chronological order.</p>
<p class="l-es">Esta edición organiza la cobertura de la República Dominicana en periódicos estadounidenses procedente del archivo Chronicling America de la Biblioteca del Congreso. La cronología curada contiene {len(timeline)} registros de {len(papers)} periódicos, de {years[0]} a {years[1]}, en orden cronológico.</p>
<p class="l-en"><b>Article texts.</b> Full texts are vision transcriptions of the Library of Congress page scans, article only, faithful in substance: no invented headlines, no neighbouring items, unreadable passages marked [illegible]. {n_full} of {len(timeline)} records carry full text in this pilot; the rest show a summary and link to the source page while extraction continues. The short OCR excerpts shown on some pages are Library of Congress locator text, labeled as such, never presented as the article.</p>
<p class="l-es"><b>Textos de los artículos.</b> Los textos completos son transcripciones visuales de los escaneos de la Biblioteca del Congreso, solo el artículo, fieles en sustancia: sin titulares inventados, sin textos vecinos, pasajes ilegibles marcados [illegible]. {n_full} de {len(timeline)} registros llevan texto completo en este piloto; el resto muestra un resumen y el enlace a la página fuente mientras continúa la extracción.</p>
<p class="l-en"><b>Evidence labels.</b> Claims on this site are labeled by basis: <span class="label doc">Documented</span> for material substantiated by a cited primary source, and <span class="label oral">Oral tradition / loosely verified</span> for family or oral accounts that may or may not be accurate, spelled out for the high-scrutiny reader.</p>
<p class="l-es"><b>Etiquetas de evidencia.</b> Las afirmaciones de este sitio se etiquetan según su base: documentado, para material sustentado por una fuente primaria citada, y tradición oral / verificación parcial, para relatos familiares u orales que pueden o no ser exactos.</p>
<p class="l-en"><b>Provenance.</b> Every article page carries its record id and SHA-256 digests of the source material, and links to the Library of Congress page scan.</p>
</div>""")
    h.append("</article></div>")
    h.append(FOOT)
    return "".join(h)

def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "articles"))
    os.makedirs(os.path.join(OUT, "era"))
    os.makedirs(os.path.join(OUT, "assets", "maritime"))
    open(os.path.join(OUT, "assets", "style.css"), "w", encoding="utf-8").write(CSS)
    if os.path.isdir(BASSETS):
        for f in os.listdir(BASSETS):
            shutil.copy2(os.path.join(BASSETS, f), os.path.join(OUT, "assets", "maritime", f))
    for i, r in enumerate(timeline):
        prev_r = timeline[i - 1] if i > 0 else None
        next_r = timeline[i + 1] if i < len(timeline) - 1 else None
        open(os.path.join(OUT, "articles", r["id"] + ".html"), "w", encoding="utf-8").write(article_page(r, prev_r, next_r))
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(index_page())
    open(os.path.join(OUT, "eras.html"), "w", encoding="utf-8").write(eras_page())
    open(os.path.join(OUT, "maritime.html"), "w", encoding="utf-8").write(maritime_page())
    open(os.path.join(OUT, "method.html"), "w", encoding="utf-8").write(method_page())
    open(os.path.join(OUT, "assets", "search-index.json"), "w", encoding="utf-8").write(search_index())
    ep = era_pages()
    for name, html in ep.items():
        open(os.path.join(OUT, "era", name), "w", encoding="utf-8").write(html)
    total_cards = sum(len(era_records[e]) for e in era_names)
    print(f"pilot built: {len(timeline)} article pages, {n_full} with full text, {len(papers)} newspapers, {years[0]}-{years[1]}; era browse pages: {len(ep)} carrying {total_cards} cards")

if __name__ == "__main__":
    main()
