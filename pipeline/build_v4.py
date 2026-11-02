#!/usr/bin/env python3
"""Build the xmella.me US/DR Newspaper Timeline site - v4.

Implements PiK0's v4 rulings (2026-11-01 night):
- Design for human beings: NO technical apparatus on public pages (no
  digests, no hashes, no OCR/method jargon). Sources are cited the way a
  human publication cites them. The build-time digest gate stays in the
  workshop as an integrity check; it is never printed.
- Walnut #4A2E20 + Terracotta #B8602F palette (Mustard/Sage rare accents),
  parchment reading paper in light mode, walnut room in dark mode, with a
  light/dark toggle.
- Spanish is the default language; the language buttons carry flag
  graphics (Spain for ES, Union Jack for EN, his explicit choice).
- 407 FYI design cues: Book Cover framed masthead, beveled-plate cards,
  plate photo format, section rhythm.
- Mella Maritime leaves this branch entirely (Grandpa Tito gets his own
  standalone page off the xmella.me launch screen).
- Every article page carries a Send Observation box (mailto
  admin@xmella.me, article prefilled).
- Human copy throughout (the 407 "don't sound like AI" concepts).

Inputs (audited sources only):
  - bundle site/data/timeline.json (1,418 records, EN/ES summaries)
  - bundle site/data/eras.json (era narratives; counts NEVER taken from it)
  - full corpus records.jsonl (full excerpts + LCCN, for facets/citation)
  - data/extraction*.jsonl (lane extractions, latest row per id)
Output: ~/workspace/chronicling-america/pilot-site/ (static)
Counts are computed from the data, never hard-coded. The build FAILS if
any displayed excerpt digest does not recompute from the displayed text
(workshop check only).
"""
import json, glob, hashlib, os, re, shutil, sys
from html import escape as esc

BASE = os.path.expanduser("~/workspace/chronicling-america")
BDATA = os.path.join(BASE, "handoff/bundle/site/data")
BASSETS = os.path.join(BASE, "handoff/bundle/site/assets/maritime")
CORPUS = os.path.join(BASE, "handoff/full/bundle/pipeline/s3_records/output/records.jsonl")
OUT = os.path.join(BASE, "pilot-site")
PAGE_SIZE = 100
SITE_BASE = "https://xmella.me/us-dr-newspaper-timeline/"

# From the adversarial review evidence (04_extraction_audit): low
# containment of the transcription in its page OCR. cr19774-2 is held
# (signature absent from page OCR); the others are flagged on-page.
QA_HOLD = {"cr19774-2"}
QA_FLAG = {"cr10985-1", "cr00232-2"}
# Review Front 3 exhibits: summaries with major fidelity defects.
QUARANTINE_KNOWN = {"cr38078-1", "cr22764-1", "cr31849-1", "cr06650-1", "cr23239-2"}

def load_json(p):
    d = json.load(open(p, encoding="utf-8"))
    return d if isinstance(d, list) else d.get("records", [])

timeline = load_json(os.path.join(BDATA, "timeline.json"))
eras = load_json(os.path.join(BDATA, "eras.json"))
maritime = load_json(os.path.join(BDATA, "maritime_records.json"))

# full corpus excerpts + LCCN (provenance display + newspaper directory)
corpus = {}
with open(CORPUS, encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        corpus[r["record_id"]] = {"excerpt": r.get("excerpt") or "",
                                  "sha": r.get("excerpt_sha256") or "",
                                  "lccn": r.get("lccn") or ""}

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

def is_full(r):
    e = ext.get(r["id"], {})
    return bool(e.get("status") == "ok" and e.get("article_text"))

def display_name(r):
    e = ext.get(r["id"], {})
    if is_full(r) and e.get("headline_as_printed"):
        return e["headline_as_printed"]
    return r["newspaper"]

n_full = sum(1 for r in timeline if is_full(r))
papers = sorted({r["newspaper"] for r in timeline})
years = (timeline[0]["date"][:4], timeline[-1]["date"][:4])
topics_all = sorted({t for r in timeline for t in (r.get("topics") or [])})
places_all = sorted({r["place"] for r in timeline})
era_names = []
for r in timeline:
    if r["era"] not in era_names:
        era_names.append(r["era"])

def slugify(s):
    s = re.sub(r"[áàä]", "a", s); s = re.sub(r"[éèë]", "e", s)
    s = re.sub(r"[íìï]", "i", s); s = re.sub(r"[óòö]", "o", s)
    s = re.sub(r"[úùü]", "u", s); s = re.sub(r"ñ", "n", s)
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "x"

def unique_slugs(names):
    out, seen = {}, {}
    for n in names:
        s = slugify(n)
        if s in seen:
            seen[s] += 1
            s = f"{s}-{seen[s]}"
        else:
            seen[s] = 1
        out[n] = s
    return out

era_slug = unique_slugs(era_names)
paper_slug = unique_slugs(papers)
topic_slug = unique_slugs(topics_all)
place_slug = unique_slugs(places_all)
era_records = {e: [r for r in timeline if r["era"] == e] for e in era_names}
paper_records = {p: [r for r in timeline if r["newspaper"] == p] for p in papers}
topic_records = {t: [r for r in timeline if t in (r.get("topics") or [])] for t in topics_all}
place_records = {p: [r for r in timeline if r["place"] == p] for p in places_all}

def npages(rs):
    return max(1, (len(rs) + PAGE_SIZE - 1) // PAGE_SIZE)

# --- window-bleed detector v1: >=2 headline-like lines in the passage ---
HEADLINE_RE = re.compile(r"^[A-Z][A-Z0-9 ,.'&\-]{11,}$")
def bleed_suspect(text):
    hits = 0
    for line in (text or "").split("\n"):
        line = line.strip()
        if len(line) >= 12 and HEADLINE_RE.match(line) and sum(c.isalpha() for c in line) >= 8:
            hits += 1
    return hits >= 2

QUARANTINE = set(QUARANTINE_KNOWN)
FLAG_BLEED = set()
for r in timeline:
    if bleed_suspect(corpus.get(r["id"], {}).get("excerpt", "")):
        FLAG_BLEED.add(r["id"])
# The regeneration priority queue: withheld + screen-flagged records.
with open(os.path.join(BASE, "data/summary-regeneration-queue.json"), "w", encoding="utf-8") as f:
    json.dump({"withheld_failed_fidelity_check": sorted(QUARANTINE),
               "flagged_window_bleed_screen": sorted(FLAG_BLEED - QUARANTINE)},
              f, indent=1)
print(f"summary queue: {len(QUARANTINE)} withheld (failed fidelity check), "
      f"{len(FLAG_BLEED - QUARANTINE)} flagged by the bleed screen")

# --- digest gate: every displayed excerpt must recompute its digest ---
gate_ok = 0
for r in timeline:
    c = corpus.get(r["id"], {})
    if c.get("excerpt") and hashlib.sha256(c["excerpt"].encode("utf-8")).hexdigest() == r.get("excerpt_sha256") == c.get("sha"):
        gate_ok += 1
if gate_ok != len(timeline):
    print(f"BUILD FAILED: excerpt digest gate {gate_ok}/{len(timeline)}")
    sys.exit(1)
print(f"digest gate: {gate_ok}/{len(timeline)} displayed excerpts recompute their SHA-256")

CSS = """
:root{
--paper:#F7F1E3;--paper-elevated:#FDF9EF;--paper-muted:#EFE5CF;
--ink:#2A1C11;--ink-secondary:#5C4632;--ink-muted:#7A6350;
--walnut:#4A2E20;--walnut-deep:#38220F;--terracotta:#B8602F;--terracotta-bright:#C96F3B;
--mustard:#C99B40;--sage:#7C8C5C;
--border:#D9C9A8;--border-strong:#B39B74;
--plate-hi:#FFFDF6;--plate-lo:#E4D5B8;
--shadow:0 1px 2px rgba(74,46,32,.18),0 4px 14px rgba(74,46,32,.10)}
body[data-theme="dark"]{
--paper:#221407;--paper-elevated:#2E1B0E;--paper-muted:#3A2412;
--ink:#F3E7D3;--ink-secondary:#D8C3A5;--ink-muted:#B89B78;
--walnut:#170C04;--walnut-deep:#12090302;--terracotta:#D07B45;--terracotta-bright:#E08D54;
--border:#5A4030;--border-strong:#7A5B40;
--plate-hi:#3D2716;--plate-lo:#1D1106;
--shadow:0 1px 2px rgba(0,0,0,.5),0 4px 14px rgba(0,0,0,.4)}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Segoe UI","Source Sans 3",-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.6;
transition:background .25s ease,color .25s ease}
a{color:var(--terracotta)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}
/* Book Cover masthead: closed double-rule frame, rounded corners */
header.masthead{margin:18px auto 0;max-width:1080px;background:var(--paper-elevated);
border:2px solid var(--walnut);border-radius:20px;padding:10px;
box-shadow:var(--shadow)}
header.masthead .frame{border:1px solid var(--border-strong);border-radius:13px;
padding:26px 20px 20px;text-align:center}
header.masthead .kicker{letter-spacing:.18em;font-size:12px;color:var(--ink-secondary);text-transform:uppercase}
header.masthead h1,header.masthead .sitename{margin:6px 0 4px;font-size:clamp(26px,4.5vw,42px);font-weight:700;color:var(--ink)}
header.masthead .sub{color:var(--ink-secondary);font-size:15px;max-width:720px;margin:0 auto}
.utilbar{display:flex;gap:10px;justify-content:center;align-items:center;padding:12px 10px 4px;flex-wrap:wrap}
.utilbar button{font:inherit;font-size:13px;font-weight:600;padding:8px 14px;min-height:44px;
border:1px solid var(--border-strong);background:var(--paper-elevated);color:var(--ink);
border-radius:999px;cursor:pointer;display:inline-flex;align-items:center;gap:8px}
.utilbar button[aria-pressed="true"]{background:var(--terracotta);color:#FFF7EA;border-color:var(--terracotta)}
.utilbar button svg{width:22px;height:15px;border-radius:2px;box-shadow:0 0 0 1px rgba(0,0,0,.25);flex:none}
.utilbar .sep{width:1px;height:24px;background:var(--border-strong)}
nav.main{display:flex;gap:18px;justify-content:center;padding:12px 10px;font-size:14px;font-weight:600;flex-wrap:wrap}
nav.main a{color:var(--ink);text-decoration:none;padding:6px 2px}
nav.main a:hover{color:var(--terracotta)}
.stats{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;margin:22px 0}
.stat{background:var(--paper-elevated);border:1px solid var(--border);border-radius:10px;
padding:10px 18px;text-align:center;min-width:130px;box-shadow:var(--shadow)}
.stat b{display:block;font-size:22px}
.stat span{font-size:12px;color:var(--ink-secondary);text-transform:uppercase;letter-spacing:.08em}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}
.controls input[type="search"],.controls select{font:inherit;font-size:14px;padding:8px 10px;
border:1px solid var(--border-strong);background:var(--paper-elevated);color:var(--ink);border-radius:8px}
.controls input[type="search"]{flex:1;min-width:200px}
/* Beveled plate cards */
.card{background:linear-gradient(180deg,var(--plate-hi),var(--paper-elevated) 55%);
border:1px solid var(--border-strong);border-radius:10px;padding:16px 18px;margin:0 0 14px;
box-shadow:inset 0 1px 0 rgba(255,255,255,.45),inset 0 -8px 14px -10px var(--plate-lo),var(--shadow)}
.card .meta{font-size:13px;color:var(--ink-secondary)}
.card h3{margin:4px 0 6px;font-size:18px}
.card h3 a{color:var(--ink);text-decoration:none}
.card h3 a:hover{color:var(--terracotta)}
.pills{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.pill{font-size:11px;font-weight:600;letter-spacing:.03em;border:1px solid var(--border-strong);border-radius:999px;padding:2px 9px;color:var(--ink-secondary)}
.pill.full{border-color:var(--terracotta);color:var(--terracotta)}
article.page{background:var(--paper-elevated);border:1px solid var(--border);border-radius:12px;
padding:26px 30px;margin-top:22px;box-shadow:var(--shadow)}
article.page h1{font-size:26px;margin:6px 0}
article.page .src{font-size:14px;color:var(--ink-secondary);border-bottom:1px solid var(--border);padding-bottom:12px}
article.page .body p{margin:0 0 14px;font-size:16px}
.well{background:var(--paper-muted);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:16px 0}
.well h4{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-secondary)}
.label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.05em;padding:2px 8px;border-radius:3px;text-transform:uppercase}
.label.doc{background:var(--sage);color:#fff}
.label.oral{background:var(--terracotta);color:#fff}
.sumlabel{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--terracotta);margin:0 0 4px}
.prevnext{display:flex;justify-content:space-between;gap:12px;margin-top:22px;font-size:14px}
/* Plate: photo in a mat, caption + credit inside the mat */
figure.plate{margin:18px 0;text-align:center;background:var(--paper-elevated);
border:1px solid var(--border-strong);border-radius:10px;padding:14px;box-shadow:var(--shadow)}
figure.plate img{max-width:100%;border:1px solid var(--border-strong)}
figure.plate figcaption{font-size:13px;color:var(--ink-secondary);margin-top:8px}
/* Send Observation box */
.observe{margin:22px 0 4px;background:linear-gradient(180deg,var(--plate-hi),var(--paper-elevated) 60%);
border:1px solid var(--walnut);border-radius:12px;padding:6px;box-shadow:var(--shadow)}
.observe .inner{border:1px solid var(--border-strong);border-radius:8px;padding:16px 18px;text-align:center}
.observe h4{margin:0 0 6px;font-size:16px}
.observe p{margin:0 0 12px;font-size:14px;color:var(--ink-secondary)}
.observe a.btn{display:inline-block;font-weight:700;font-size:14px;padding:10px 22px;min-height:44px;
background:var(--terracotta);color:#FFF7EA;border-radius:999px;text-decoration:none}
.observe a.btn:hover{background:var(--terracotta-bright)}
footer{margin:40px auto 18px;max-width:1080px;background:var(--paper-elevated);
border:2px solid var(--walnut);border-radius:20px;padding:8px;box-shadow:var(--shadow)}
footer .frame{border:1px solid var(--border-strong);border-radius:13px;padding:14px 20px;
text-align:center;font-size:13px;color:var(--ink-secondary)}
.pager{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:center;margin:20px 0}
.pager a,.pager span.cur{font-size:13px;font-weight:600;padding:10px 14px;min-height:44px;border:1px solid var(--border-strong);border-radius:999px;text-decoration:none;color:var(--ink);background:var(--paper-elevated)}
.pager span.cur{background:var(--terracotta);color:#FFF7EA;border-color:var(--terracotta)}
.pager .range{width:100%;text-align:center;font-weight:400;border:none;background:none;font-size:13px;color:var(--ink-secondary)}
.morebtn{display:block;margin:6px auto 20px;font:inherit;font-size:14px;font-weight:600;padding:10px 22px;min-height:44px;border:1px solid var(--border-strong);background:var(--paper-elevated);color:var(--ink);border-radius:999px;cursor:pointer}
.dirlist{columns:2;column-gap:28px;font-size:14px}
.dirlist div{break-inside:avoid;margin:0 0 6px}
.catnum{font-size:12px;color:var(--ink-muted)}
@media (max-width:640px){.dirlist{columns:1}article.page{padding:18px 16px}header.masthead{margin:10px 10px 0}footer{margin:30px 10px 12px}}
body[data-lang="en"] .l-es{display:none}
body[data-lang="es"] .l-en{display:none}
.hidden{display:none}
"""

def L(en, es):
    return f'<span class="l-en">{esc(en)}</span><span class="l-es">{esc(es)}</span>'

FLAG_ES = ('<svg viewBox="0 0 22 15" aria-hidden="true"><rect width="22" height="15" fill="#F1BF00"/>'
           '<rect width="22" height="3.75" fill="#AA151B"/><rect y="11.25" width="22" height="3.75" fill="#AA151B"/></svg>')
FLAG_GB = ('<svg viewBox="0 0 22 15" aria-hidden="true"><rect width="22" height="15" fill="#012169"/>'
           '<path d="M0 0L22 15M22 0L0 15" stroke="#fff" stroke-width="3"/>'
           '<path d="M0 0L22 15M22 0L0 15" stroke="#C8102E" stroke-width="1.2"/>'
           '<path d="M11 0V15M0 7.5H22" stroke="#fff" stroke-width="5"/>'
           '<path d="M11 0V15M0 7.5H22" stroke="#C8102E" stroke-width="2.8"/></svg>')

def head(title, depth=0, site_h1=False, desc="", extra_meta=""):
    css = ("../" * depth) + "assets/style.css"
    title_html = "<h1>US/DR Newspaper Timeline</h1>" if site_h1 else '<p class="sitename">US/DR Newspaper Timeline</p>'
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(desc or title)}">
<title>{esc(title)} | US/DR Newspaper Timeline</title>{extra_meta}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css}"></head>
<body data-lang="es" data-theme="light">
<script>(function(){{var l=localStorage.getItem('xm-lang');if(l){{document.body.dataset.lang=l;document.documentElement.lang=l;}}
var t=localStorage.getItem('xm-theme');if(!t&&window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)t='dark';
if(t)document.body.dataset.theme=t;}})();</script>
<header class="masthead"><div class="frame"><div class="kicker">{years[0]}&ndash;{years[1]} &middot; {L("Library of Congress", "Biblioteca del Congreso")} &middot; Chronicling America</div>
{title_html}
<div class="sub">{L("The Dominican Republic in the American Press: United States newspaper coverage of the island, gathered and translated for readers in both languages", "La República Dominicana en la prensa estadounidense: la cobertura de la isla en los periódicos de Estados Unidos, reunida y traducida para lectores en ambos idiomas")}</div></div></header>
<div class="utilbar">
<button id="btn-es" aria-pressed="true" onclick="setLang('es')">{FLAG_ES} Español</button>
<button id="btn-en" aria-pressed="false" onclick="setLang('en')">{FLAG_GB} English</button>
<span class="sep"></span>
<button id="btn-theme" aria-pressed="false" onclick="toggleTheme()">{L("Dark", "Oscuro")} / {L("Light", "Claro")}</button></div>
<script>function setLang(l){{document.body.dataset.lang=l;document.documentElement.lang=l;document.getElementById('btn-en').setAttribute('aria-pressed',l=='en');document.getElementById('btn-es').setAttribute('aria-pressed',l=='es');localStorage.setItem('xm-lang',l);}}
function toggleTheme(){{var d=document.body.dataset.theme=='dark'?'light':'dark';document.body.dataset.theme=d;document.getElementById('btn-theme').setAttribute('aria-pressed',d=='dark');localStorage.setItem('xm-theme',d);}}
(function(){{document.addEventListener('DOMContentLoaded',function(){{var l=document.body.dataset.lang;setLang(l);
document.getElementById('btn-theme').setAttribute('aria-pressed',document.body.dataset.theme=='dark');}});}})();</script>
"""

def nav(depth=0):
    p = "../" * depth
    return f"""<nav class="main"><a href="{p}index.html">{L("Timeline", "Cronología")}</a>
<a href="{p}eras.html">{L("Eras", "Épocas")}</a>
<a href="{p}papers.html">{L("Newspapers", "Periódicos")}</a>
<a href="{p}topics.html">{L("Topics", "Temas")}</a>
<a href="{p}places.html">{L("Places", "Lugares")}</a>
<a href="{p}method.html">{L("About & Sources", "Acerca de y fuentes")}</a></nav>"""

FOOT = """<footer><div class="frame">US/DR Newspaper Timeline &middot; xmella.me<br>
<span class="l-en">Every article links back to its original page at the Library of Congress. Observations and corrections are welcome: <a href="mailto:admin@xmella.me">admin@xmella.me</a></span><span class="l-es">Cada artículo enlaza a su página original en la Biblioteca del Congreso. Observaciones y correcciones son bienvenidas: <a href="mailto:admin@xmella.me">admin@xmella.me</a></span></div></footer>
</body></html>"""

def paras(text):
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)

def clean_article_text(r, e):
    """Strip a headline repeated at the start of the article text (M4)."""
    text = e.get("article_text") or ""
    head_line = (e.get("headline_as_printed") or "").strip()
    if head_line:
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        lines = text.split("\n")
        if lines and norm(lines[0]) == norm(head_line):
            return "\n".join(lines[1:]).lstrip(), True
        if norm(text[:len(head_line) + 8]).startswith(norm(head_line)) and len(text) > len(head_line):
            return text[len(head_line):].lstrip(" .\n"), True
    return text, False

STRIPPED = 0

def summary_block(r, in_card=False):
    """The reading layer for records whose full article is still being
    prepared, said plainly (v4)."""
    if r["id"] in QUARANTINE:
        return (f'<p class="sumlabel">{L("Summary on hold", "Resumen en espera")}</p>'
                f'<p>{L("The summary we first wrote for this article did not match it closely enough, so we are not showing it. The passage found on the page is below, and the original page is one click away, until the article itself is ready.", "El primer resumen que escribimos para este artículo no coincidía lo bastante con su contenido, así que no lo mostramos. Abajo está el pasaje encontrado en la página, y la página original está a un clic, hasta que el artículo mismo esté listo.")}</p>')
    out = (f'<p class="sumlabel">{L("Summary", "Resumen")}</p>'
           f'<p class="l-en">{esc(r.get("summary") or "")}</p><p class="l-es">{esc(r.get("summary_es") or "")}</p>')
    if r["id"] in FLAG_BLEED:
        out += (f'<p class="meta">{L("A note: the passage found for this article seems to run into the item beside it on the page, so read this summary as a first pass until the article itself is ready.", "Una nota: el pasaje encontrado para este artículo parece mezclarse con el texto vecino en la página, así que lea este resumen como una primera versión hasta que el artículo mismo esté listo.")}</p>')
    return out

def card(r, depth=0):
    p = "../" * depth
    topics = " ".join(r.get("topics") or [])
    pills = "".join(f'<span class="pill">{esc(t)}</span>' for t in (r.get("topics") or []))
    if is_full(r):
        e = ext[r["id"]]
        text, _ = clean_article_text(r, e)
        lead = re.sub(r"\s+", " ", text).strip()[:240]
        body = f"<p>{esc(lead)}&hellip;</p>"
        pills += f'<span class="pill full">{L("Full text", "Texto completo")}</span>'
    else:
        body = summary_block(r, in_card=True)
    return (f'<div class="card" data-topics="{esc(topics)}">'
            f'<div class="meta">{esc(r["date"])} &middot; {esc(r["place"])} &middot; {esc(r["era"])}</div>'
            f'<h3><a href="{p}articles/{esc(r["id"])}.html">{esc(display_name(r))}</a></h3>'
            f'{body}'
            f'<div class="pills">{pills}</div>'
            f'<div class="meta"><a href="{esc(r["source_url"])}">{L("See the original page", "Ver la página original")}</a></div></div>')

def excerpt_well(r):
    c = corpus.get(r["id"], {})
    if not c.get("excerpt"):
        return ""
    return (f'<div class="well"><h4>{L("From the original page", "De la página original")}</h4>'
            f'<p>{L("The passage where this article was found, copied from the newspaper page itself, reading errors and all. This is exactly what the summary above is based on.", "El pasaje donde se encontró este artículo, copiado de la propia página del periódico, con sus errores de lectura y todo. Esto es exactamente aquello en lo que se basa el resumen de arriba.")}</p>'
            f'{paras(c["excerpt"])}</div>')

def observe_box(r):
    from urllib.parse import quote
    subj = quote(f'Observation: {r["newspaper"]}, {r["date"]}')
    body = quote(f'{display_name(r)} ({r["date"]})\n{SITE_BASE}articles/{r["id"]}.html\n\n')
    return (f'<div class="observe"><div class="inner">'
            f'<h4>{L("Send an observation", "Enviar una observación")}</h4>'
            f'<p>{L("Does this article connect with your family, your town, or something you know? Did we get something wrong? Write to us. Observations go to the editor\'s inbox and are read by a person.", "¿Este artículo conecta con su familia, su pueblo o algo que usted conoce? ¿Nos equivocamos en algo? Escríbanos. Las observaciones llegan al buzón del editor y las lee una persona.")}</p>'
            f'<a class="btn" href="mailto:admin@xmella.me?subject={subj}&body={body}">{L("Send observation", "Enviar observación")}</a>'
            f'</div></div>')

def article_page(r, prev_r, next_r):
    global STRIPPED
    e = ext.get(r["id"], {})
    full = is_full(r)
    name = display_name(r)
    dc = (f'<meta name="DC.title" content="{esc(name)}">'
          f'<meta name="DC.publisher" content="{esc(r["newspaper"])}">'
          f'<meta name="DC.date" content="{esc(r["date"])}">'
          f'<meta name="DC.source" content="{esc(r["source_url"])}">'
          f'<meta name="DC.identifier" content="{esc(r["id"])}">')
    h = [head(name, depth=1, desc=f'{r["newspaper"]}, {r["date"]} - US/DR Newspaper Timeline record {r["id"]}', extra_meta=dc),
         nav(depth=1), '<div class="wrap"><article class="page">']
    h.append(f'<div class="meta">{esc(r["date"])} &middot; {esc(r["place"])} &middot; {esc(r["era"])}</div>')
    h.append(f"<h1>{esc(name)}</h1>")
    h.append(f'<div class="src">{L("Source", "Fuente")}: {esc(r["newspaper"])}, {esc(r["place"])}, {esc(r["date"])}<br>'
             f'<a href="{esc(r["source_url"])}">{esc(r["source_url"])}</a></div>')
    topics = r.get("topics") or []
    if topics:
        h.append('<div class="pills">' + "".join(f'<span class="pill">{esc(t)}</span>' for t in topics) + "</div>")
    if r["id"] in QA_HOLD:
        h.append(f'<div class="well"><h4>{L("Still being checked", "Aún en revisión")}</h4>'
                 f'<p>{L("We are still comparing this article\'s text against the original page, so the full text is not shown yet. The summary, the passage from the page, and the page itself are here in the meantime.", "Todavía estamos comparando el texto de este artículo con la página original, así que el texto completo aún no se muestra. Mientras tanto están aquí el resumen, el pasaje de la página y la página misma.")}</p></div>')
        h.append(f'<div class="body">{summary_block(r)}</div>')
    elif full:
        text, stripped = clean_article_text(r, e)
        if stripped:
            STRIPPED += 1
        h.append(f'<div class="body">{paras(text)}</div>')
        if e.get("dateline"):
            h.append(f'<div class="well"><h4>{L("Dateline as printed", "Lugar y fecha según el original")}</h4><p>{esc(e["dateline"])}</p></div>')
        if r["id"] in QA_FLAG:
            h.append(f'<div class="well"><h4>{L("A note on this text", "Una nota sobre este texto")}</h4>'
                     f'<p>{L("We are still confirming this text line by line against the original page. If a sentence reads oddly, check it against the page linked above.", "Todavía estamos confirmando este texto línea por línea contra la página original. Si alguna frase se lee rara, contrástela con la página enlazada arriba.")}</p></div>')
    else:
        h.append(f'<div class="body">{summary_block(r)}</div>')
        h.append(f'<div class="well"><h4>{L("Where this stands", "En qué punto está")}</h4><p>{L("The full text of this article is still being prepared. Until it is ready, this page carries a summary, the passage found on the page, and the link to the original, which is always one click away.", "El texto completo de este artículo aún se está preparando. Hasta que esté listo, esta página lleva un resumen, el pasaje encontrado en la página y el enlace al original, que siempre está a un clic.")}</p></div>')
    h.append(excerpt_well(r))
    h.append(f'<div class="well"><h4>{L("How to cite this article", "Cómo citar este artículo")}</h4>'
             f'<p>{esc(r["newspaper"])}. ({esc(r["date"][:4])}). {esc(r["place"])}, {esc(r["date"])}. '
             f'US/DR Newspaper Timeline. Library of Congress, Chronicling America: {esc(r["source_url"])}</p></div>')
    h.append(f'<div class="well"><h4>{L("References", "Referencias")}</h4><p>Library of Congress, Chronicling America: '
             f'<a href="{esc(r["source_url"])}">{esc(r["newspaper"])}, {esc(r["date"])}</a>.</p></div>')
    h.append(observe_box(r))
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

def pager(base, k, npages_, first_date, last_date, total):
    items = [f'<span class="range">{L("Records", "Registros")} {(k-1)*PAGE_SIZE+1}&ndash;{min(k*PAGE_SIZE, total)} {L("of", "de")} {total} &middot; {esc(first_date)} &ndash; {esc(last_date)}</span>']
    if k > 1:
        items.append(f'<a href="{base}-{k-1}.html">&larr; {L("Earlier", "Anteriores")}</a>')
    for j in range(1, npages_ + 1):
        items.append(f'<span class="cur">{j}</span>' if j == k else f'<a href="{base}-{j}.html">{j}</a>')
    if k < npages_:
        items.append(f'<a href="{base}-{k+1}.html">{L("Later", "Siguientes")} &rarr;</a>')
    return f'<div class="pager">{"".join(items)}</div>'

def listing_pages(kind_dir, base, title, rs, crumb):
    """Paginated record listings for one facet value. Returns {filename: html}."""
    out = {}
    npg = npages(rs)
    for k in range(1, npg + 1):
        chunk = rs[(k - 1) * PAGE_SIZE: k * PAGE_SIZE]
        h = [head(f"{title} ({k}/{npg})", depth=1), nav(depth=1), '<div class="wrap">']
        h.append(f'<div class="meta" style="margin-top:18px">{crumb} &middot; {L("Page", "Página")} {k} {L("of", "de")} {npg}</div>')
        h.append(f"<h1>{esc(title)}</h1>")
        h.append(pager(base, k, npg, chunk[0]["date"], chunk[-1]["date"], len(rs)))
        h.append("".join(card(r, depth=1) for r in chunk))
        h.append(pager(base, k, npg, chunk[0]["date"], chunk[-1]["date"], len(rs)))
        h.append("</div>")
        h.append(FOOT)
        out[f"{base}-{k}.html"] = "".join(h)
    return out

def era_pages():
    out = {}
    for era in era_names:
        crumb = f'<a href="../eras.html">{L("Eras", "Épocas")}</a>'
        out.update(listing_pages("era", era_slug[era], era, era_records[era], crumb))
    return out

def facet_pages():
    out = {}
    for p in papers:
        out[f"paper/{paper_slug[p]}-1.html"] = None  # placeholder replaced below
    out = {}
    for p in papers:
        for name, html in listing_pages("paper", paper_slug[p], p, paper_records[p],
                                        f'<a href="../papers.html">{L("Newspapers", "Periódicos")}</a>').items():
            out[f"paper/{name}"] = html
    for t in topics_all:
        for name, html in listing_pages("topic", topic_slug[t], t, topic_records[t],
                                        f'<a href="../topics.html">{L("Topics", "Temas")}</a>').items():
            out[f"topic/{name}"] = html
    for pl in places_all:
        for name, html in listing_pages("place", place_slug[pl], pl, place_records[pl],
                                        f'<a href="../places.html">{L("Places", "Lugares")}</a>').items():
            out[f"place/{name}"] = html
    return out

def search_index():
    rows = []
    for r in timeline:
        if is_full(r):
            text, _ = clean_article_text(r, ext[r["id"]])
            s = re.sub(r"\s+", " ", text).strip()[:240]
            x = s
        elif r["id"] in QUARANTINE:
            s = x = ""
        else:
            s = (r.get("summary") or "")[:240]
            x = (r.get("summary_es") or "")[:240]
        rows.append({"i": r["id"], "d": r["date"], "n": r["newspaper"], "p": r["place"],
                     "e": r["era"], "t": r.get("topics") or [], "h": display_name(r),
                     "f": 1 if is_full(r) else 0, "s": s, "x": x})
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

def index_page():
    eras_with = [e for e in era_names if era_records[e]]
    eras_bg = [e for e in era_names if not era_records[e]]
    h = [head("Timeline", site_h1=True, desc="US/DR Newspaper Timeline: a bilingual research edition of US newspaper coverage of the Dominican Republic, 1820-1963, from Library of Congress Chronicling America."), nav()]
    h.append('<div class="wrap">')
    h.append('<div class="stats">'
             f'<div class="stat"><b>{len(timeline)}</b><span>{L("Articles", "Artículos")}</span></div>'
             f'<div class="stat"><b>{len(papers)}</b><span>{L("Newspapers", "Periódicos")}</span></div>'
             f'<div class="stat"><b>{years[0]}-{years[1]}</b><span>{L("Years covered", "Años")}</span></div>'
             f'<div class="stat"><b>{n_full}</b><span>{L("Full texts ready", "Textos completos")}</span></div>'
             f'<div class="stat"><b>{len(eras_with)}+{len(eras_bg)}</b><span>{L("Eras + background", "Épocas + contexto")}</span></div></div>')
    h.append(f'<div class="card"><p class="l-en">For over a century, American newspapers kept a close eye on the Dominican Republic: its ports and presidents, its sugar and its storms, its revolutions and its baseball. This site gathers that coverage in one place, in the order it appeared, in English and Spanish. Some articles are here in full; the rest carry a summary and the passage it came from, with the original page always one click away. The collection is still growing, and readers who know something we don\'t are invited to send an observation from any article page.</p>'
             f'<p class="l-es">Durante más de un siglo, los periódicos estadounidenses siguieron de cerca a la República Dominicana: sus puertos y presidentes, su azúcar y sus tormentas, sus revoluciones y su béisbol. Este sitio reúne esa cobertura en un solo lugar, en el orden en que apareció, en inglés y en español. Algunos artículos están aquí completos; los demás llevan un resumen y el pasaje del que salió, con la página original siempre a un clic. La colección sigue creciendo, y quien sepa algo que nosotros no sabemos puede enviar una observación desde cualquier página de artículo.</p></div>')
    h.append(f"""<div class="controls">
<input type="search" id="q" placeholder="{L("Search headlines, papers, places, summaries", "Buscar titulares, periódicos, lugares, resúmenes")}">
</div>
<div class="meta" id="count">{L("Search the full timeline (accents optional), or browse by era, newspaper, topic, or place. Results appear 50 at a time.", "Busque en toda la cronología (acentos opcionales) o explore por época, periódico, tema o lugar. Los resultados aparecen de 50 en 50.")}</div>
<div id="results"></div>
<button class="morebtn hidden" id="more">{L("Show more results", "Mostrar más resultados")}</button>""")
    h.append(f'<h2 style="margin-top:28px">{L("Browse by era", "Explorar por época")}</h2>')
    era_meta = {e.get("era_key") or e.get("title_en"): e for e in eras}
    for era in era_names:
        rs = era_records[era]
        em = era_meta.get(era, {})
        yrs = em.get("years") or (f'{rs[0]["date"][:4]}-{rs[-1]["date"][:4]}' if rs else "")
        if rs:
            h.append(f'<div class="card"><div class="meta">{L("Historical period", "Período histórico")}: {esc(yrs)} &middot; {len(rs)} {L("records", "registros")} &middot; {npages(rs)} {L("pages", "páginas")}</div>'
                     f'<h3><a href="era/{era_slug[era]}-1.html">{esc(era)}</a></h3>'
                     f'<p class="l-en">{esc(em.get("summary_en") or "")}</p><p class="l-es">{esc(em.get("summary_es") or "")}</p></div>')
        else:
            h.append(f'<div class="card"><div class="meta">{L("Historical period", "Período histórico")}: {esc(yrs)} &middot; {L("Background chapter - no records in this collection", "Capítulo de contexto - sin registros en esta colección")}</div>'
                     f'<h3><a href="eras.html">{esc(era)}</a></h3>'
                     f'<p class="l-en">{esc(em.get("summary_en") or "")}</p><p class="l-es">{esc(em.get("summary_es") or "")}</p></div>')
    h.append(f'<h2 style="margin-top:28px">{L("Browse the catalog", "Explorar el catálogo")}</h2>')
    h.append(f'<div class="card"><p><a href="papers.html">{L("Newspapers", "Periódicos")}</a> ({len(papers)}) &middot; '
             f'<a href="topics.html">{L("Topics", "Temas")}</a> ({len(topics_all)}) &middot; '
             f'<a href="places.html">{L("Places", "Lugares")}</a> ({len(places_all)})</p></div>')
    h.append(r"""</div>
<script>
var q=document.getElementById('q'),res=document.getElementById('results'),cnt=document.getElementById('count'),
more=document.getElementById('more'),IDX=null,matches=[],shown=0,STEP=50;
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function fold(s){return (s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');}
function render(){var lang=document.body.dataset.lang||'en';
res.innerHTML=matches.slice(0,shown).map(function(m){
return '<div class="card"><div class="meta">'+esc(m.d)+' &middot; '+esc(m.p)+' &middot; '+esc(m.e)+'</div>'+
'<h3><a href="articles/'+m.i+'.html">'+esc(m.h)+'</a></h3>'+
'<p>'+esc(lang=='es'?(m.x||m.s):m.s)+'</p>'+
(m.f?'<div class="pills"><span class="pill full">'+(lang=='es'?'Texto completo':'Full text')+'</span></div>':'')+
'</div>';}).join('');
cnt.textContent=matches.length+' / '+IDX.length;
more.classList.toggle('hidden',shown>=matches.length);}
function run(){if(!IDX)return;var toks=fold(q.value).split(/\s+/).filter(Boolean);
if(!toks.length){matches=[];shown=0;res.innerHTML='';cnt.textContent='';more.classList.add('hidden');return;}
matches=IDX.filter(function(m){var hay=fold(m.d+' '+m.n+' '+m.p+' '+m.e+' '+m.h+' '+m.s+' '+m.x+' '+(m.t||[]).join(' '));
return toks.every(function(t){return hay.indexOf(t)>-1;});});
shown=Math.min(STEP,matches.length);render();}
function load(){if(IDX){run();return;}
fetch('assets/search-index.json').then(function(r){return r.json();}).then(function(j){IDX=j;run();});}
q.addEventListener('focus',load);q.addEventListener('input',function(){IDX?run():load();});
more.addEventListener('click',function(){shown=Math.min(shown+STEP,matches.length);render();});
</script>""")
    h.append(FOOT)
    return "".join(h)

def eras_page():
    counts = {e: len(rs) for e, rs in era_records.items()}
    h = [head("Eras"), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("Era chapters", "Capítulos de época")}</h1>')
    h.append(f'<div class="well"><h4>{L("About these essays", "Sobre estos ensayos")}</h4><p>{L("The era essays are background, written to set the scene for the articles of their years. The articles are the evidence; the essays are the frame. Era ranges are historical periods, and the collection itself runs 1820-1963.", "Los ensayos de época son contexto, escritos para ambientar los artículos de sus años. Los artículos son la evidencia; los ensayos, el marco. Los rangos de época son períodos históricos, y la colección misma va de 1820 a 1963.")}</p></div>')
    for e in eras:
        key = e.get("era_key") or e.get("title_en")
        n = counts.get(key, 0)
        link = f'<a href="era/{era_slug[key]}-1.html">{L("Browse this era", "Ver esta época")}</a>' if n and key in era_slug else ""
        h.append(f'<div class="card"><div class="meta">{L("Historical period", "Período histórico")}: {esc(e.get("years") or "")} &middot; {n} {L("records", "registros")}</div>'
                 f'<h2 style="font-size:19px;margin:4px 0 6px"><span class="l-en">{esc(e.get("title_en") or "")}</span><span class="l-es">{esc(e.get("title_es") or "")}</span></h2>'
                 f'<p class="l-en">{esc(e.get("summary_en") or "")}</p><p class="l-es">{esc(e.get("summary_es") or "")}</p>{link}</div>')
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def papers_page():
    h = [head("Newspapers"), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("Newspaper directory", "Directorio de periódicos")}</h1>')
    h.append(f'<p>{L("Every newspaper title in the collection, with its Library of Congress Control Number (LCCN), publication places, and record count.", "Cada periódico de la colección, con su número de control de la Biblioteca del Congreso (LCCN), lugares de publicación y número de registros.")}</p>')
    h.append('<div class="dirlist">')
    for p in papers:
        rs = paper_records[p]
        lccns = sorted({corpus[r["id"]]["lccn"] for r in rs if corpus[r["id"]]["lccn"]})
        places_ = sorted({r["place"] for r in rs})
        h.append(f'<div><a href="paper/{paper_slug[p]}-1.html"><b>{esc(p)}</b></a> ({len(rs)})<br>'
                 f'<span class="catnum">{L("Library catalog no.", "Núm. de catálogo")} {esc(", ".join(lccns))}</span><br>{esc("; ".join(places_))} &middot; {rs[0]["date"][:4]}-{rs[-1]["date"][:4]}</div>')
    h.append('</div></div>')
    h.append(FOOT)
    return "".join(h)

def topics_page():
    h = [head("Topics"), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("Topics", "Temas")}</h1><div class="dirlist">')
    for t in topics_all:
        h.append(f'<div><a href="topic/{topic_slug[t]}-1.html"><b>{esc(t)}</b></a> ({len(topic_records[t])})</div>')
    h.append('</div></div>')
    h.append(FOOT)
    return "".join(h)

def places_page():
    h = [head("Places"), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("Places of publication", "Lugares de publicación")}</h1><div class="dirlist">')
    for pl in places_all:
        h.append(f'<div><a href="place/{place_slug[pl]}-1.html"><b>{esc(pl)}</b></a> ({len(place_records[pl])})</div>')
    h.append('</div></div>')
    h.append(FOOT)
    return "".join(h)

def method_page():
    h = [head("About & Sources"), nav(), '<div class="wrap"><article class="page">']
    h.append(f"<h1>{L('About this collection, and its sources', 'Acerca de esta colección y sus fuentes')}</h1>")
    h.append(f"""<div class="body">
<p class="l-en">Everything here comes from one place: the Library of Congress and its Chronicling America archive, which preserves American newspapers page by page. This collection gathers the coverage of the Dominican Republic: {len(timeline)} articles from {len(papers)} newspapers, {years[0]} to {years[1]}, in the order they were published. Every article page names its newspaper and date and links to the original page at the Library, so anything you read here can be checked against the source in one click.</p>
<p class="l-es">Todo lo que hay aquí viene de un solo lugar: la Biblioteca del Congreso y su archivo Chronicling America, que conserva los periódicos estadounidenses página por página. Esta colección reúne la cobertura de la República Dominicana: {len(timeline)} artículos de {len(papers)} periódicos, de {years[0]} a {years[1]}, en el orden en que se publicaron. Cada página de artículo nombra su periódico y su fecha y enlaza a la página original en la Biblioteca, así que todo lo que lea aquí puede contrastarse con la fuente en un clic.</p>
<p class="l-en"><b>Full texts and summaries.</b> Articles are still being prepared one by one. Where the full text is ready, you will see the article itself, just the article, without the items that sat beside it on the page. Where it is not ready yet, the page carries a summary, and under it the passage the summary was written from, copied from the newspaper page with its reading errors and all. A summary is labeled as a summary. Nothing here pretends to be the article when it is not.</p>
<p class="l-es"><b>Textos completos y resúmenes.</b> Los artículos se siguen preparando uno por uno. Donde el texto completo está listo, verá el artículo mismo, solo el artículo, sin los textos que tenía al lado en la página. Donde aún no está listo, la página lleva un resumen y, debajo, el pasaje del que se escribió el resumen, copiado de la página del periódico con sus errores de lectura y todo. Un resumen se etiqueta como resumen. Nada aquí finge ser el artículo cuando no lo es.</p>
<p class="l-en"><b>What belongs here.</b> An article belongs in this collection when it is substantially about the Dominican Republic, under any of its historical names, including Santo Domingo: its government, its people, its land, or its dealings with the United States and the world. Articles mainly about Haiti are included when they take up Santo Domingo or the whole island in earnest; a passing mention is not enough. In nineteenth-century newspapers the word "Dominica" often meant this country, and those cases are judged by context; the island of Dominica is a different place and stays out.</p>
<p class="l-es"><b>Qué pertenece aquí.</b> Un artículo pertenece a esta colección cuando trata sustancialmente de la República Dominicana, con cualquiera de sus nombres históricos, incluido Santo Domingo: su gobierno, su gente, su tierra o sus relaciones con Estados Unidos y el mundo. Los artículos principalmente sobre Haití se incluyen cuando abordan en serio a Santo Domingo o a la isla entera; una mención pasajera no basta. En los periódicos del siglo XIX la palabra «Dominica» a menudo nombraba a este país, y esos casos se juzgan por contexto; la isla de Dominica es otro lugar y queda fuera.</p>
<p class="l-en"><b>Two kinds of knowing.</b> Where this site states something beyond the articles themselves, it says which kind of knowledge it is. <span class="label doc">Documented</span> means a primary source backs it and is cited. <span class="label oral">Oral tradition</span> means it comes from family or community memory: valued, printed as it was told, and possibly not exact. The label travels with the claim, so a careful reader always knows what they are standing on.</p>
<p class="l-es"><b>Dos maneras de saber.</b> Cuando este sitio afirma algo más allá de los propios artículos, dice de qué clase de conocimiento se trata. Lo documentado significa que una fuente primaria lo respalda y se cita. Tradición oral significa que viene de la memoria familiar o comunitaria: se valora, se imprime tal como se contó y puede no ser exacto. La etiqueta acompaña a la afirmación, para que un lector cuidadoso sepa siempre sobre qué está parado.</p>
<p class="l-en"><b>Corrections and observations.</b> This is a living collection and it will have mistakes. Every article page has a Send Observation box; observations go to <a href="mailto:admin@xmella.me">admin@xmella.me</a> and are read by a person. If your family appears in these pages, we especially want to hear from you.</p>
<p class="l-es"><b>Correcciones y observaciones.</b> Esta es una colección viva y tendrá errores. Cada página de artículo tiene un recuadro para enviar una observación; las observaciones llegan a <a href="mailto:admin@xmella.me">admin@xmella.me</a> y las lee una persona. Si su familia aparece en estas páginas, queremos saber de usted especialmente.</p>
</div>""")
    h.append("</article></div>")
    h.append(FOOT)
    return "".join(h)

def sitemap(paths):
    items = "".join(f"<url><loc>{SITE_BASE}{esc(p)}</loc></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'

def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for d in ["articles", "era", "paper", "topic", "place", "assets"]:
        os.makedirs(os.path.join(OUT, d))
    open(os.path.join(OUT, "assets", "style.css"), "w", encoding="utf-8").write(CSS)
    written = []
    for i, r in enumerate(timeline):
        prev_r = timeline[i - 1] if i > 0 else None
        next_r = timeline[i + 1] if i < len(timeline) - 1 else None
        open(os.path.join(OUT, "articles", r["id"] + ".html"), "w", encoding="utf-8").write(article_page(r, prev_r, next_r))
        written.append(f'articles/{r["id"]}.html')
    pages = {"index.html": index_page(), "eras.html": eras_page(),
             "method.html": method_page(), "papers.html": papers_page(), "topics.html": topics_page(),
             "places.html": places_page()}
    for name, html in pages.items():
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(html)
        written.append(name)
    for name, html in era_pages().items():
        open(os.path.join(OUT, "era", name), "w", encoding="utf-8").write(html)
        written.append(f"era/{name}")
    for rel, html in facet_pages().items():
        open(os.path.join(OUT, rel), "w", encoding="utf-8").write(html)
        written.append(rel)
    open(os.path.join(OUT, "assets", "search-index.json"), "w", encoding="utf-8").write(search_index())
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(sitemap(written))
    open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}sitemap.xml\n")
    print(f"v4 built: {len(timeline)} article pages, {n_full} full text, {STRIPPED} headline repeats stripped, "
          f"{len(QUARANTINE)} summaries withheld, {len(written)} pages total, {len(papers)} papers / {len(topics_all)} topics / {len(places_all)} places")

if __name__ == "__main__":
    main()
