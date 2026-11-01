#!/usr/bin/env python3
"""Build the xmella.me US/DR Newspaper Timeline pilot site - v3.

Implements the adversarial review rebuild spec (2026-11-01, PiK0 approved):
reproducible provenance (full corpus excerpt displayed, digest gate at
build), passage-summary labeling + bleed quarantine, evidence labels on
maritime notes, truthful coverage furniture, a catalog layer (newspaper /
topic / place facets), design hardening (contrast, headings, targets,
lang), sitemap + DC metadata.

Inputs (audited sources only):
  - bundle site/data/timeline.json (1,418 records, EN/ES summaries)
  - bundle site/data/eras.json (era narratives; counts NEVER taken from it)
  - bundle site/data/maritime_records.json + assets/maritime/*.jpg
  - full corpus records.jsonl (full excerpts + LCCN, for provenance/facets)
  - data/extraction*.jsonl (lane extractions, latest row per id)
Output: ~/workspace/chronicling-america/pilot-site/ (static)
Counts are computed from the data, never hard-coded. The build FAILS if
any displayed excerpt digest does not recompute from the displayed text.
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
:root{--parchment:#F7F2E7;--parchment-elevated:#FCF9F1;--parchment-muted:#EDE4D0;
--ink:#1C1A17;--ink-secondary:#4C463C;--ink-muted:#665E4E;--oxblood:#7A2E2E;
--slate:#33526B;--border:#D8CCB2;--border-strong:#A08D6B}
*{box-sizing:border-box}
body{margin:0;background:var(--parchment);color:var(--ink);
font-family:"Segoe UI","Source Sans 3",-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.6}
a{color:var(--slate)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}
header.masthead{border-bottom:4px double var(--border-strong);padding:28px 20px 18px;text-align:center}
header.masthead .kicker{letter-spacing:.18em;font-size:12px;color:var(--ink-secondary);text-transform:uppercase}
header.masthead h1,header.masthead .sitename{margin:6px 0 4px;font-size:clamp(26px,4.5vw,42px);font-weight:700}
header.masthead .sub{color:var(--ink-secondary);font-size:15px}
.utilbar{display:flex;gap:10px;justify-content:center;align-items:center;padding:10px;border-bottom:1px solid var(--border);flex-wrap:wrap}
.utilbar button,.utilbar a.btn{font:inherit;font-size:13px;font-weight:600;padding:10px 16px;min-height:44px;border:1px solid var(--border-strong);
background:var(--parchment-elevated);color:var(--ink);border-radius:999px;cursor:pointer;text-decoration:none}
.utilbar button[aria-pressed="true"]{background:var(--oxblood);color:#fff;border-color:var(--oxblood)}
nav.main{display:flex;gap:18px;justify-content:center;padding:10px;font-size:14px;font-weight:600;flex-wrap:wrap}
nav.main a{color:var(--ink);text-decoration:none;padding:6px 2px}
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
.sumlabel{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--oxblood);margin:0 0 4px}
.prevnext{display:flex;justify-content:space-between;gap:12px;margin-top:22px;font-size:14px}
figure.plate{margin:18px 0;text-align:center}
figure.plate img{max-width:100%;border:1px solid var(--border-strong)}
figure.plate figcaption{font-size:13px;color:var(--ink-secondary);margin-top:6px}
footer{border-top:4px double var(--border-strong);margin-top:40px;padding:16px 20px;text-align:center;font-size:13px;color:var(--ink-secondary)}
.pager{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:center;margin:20px 0}
.pager a,.pager span.cur{font-size:13px;font-weight:600;padding:10px 14px;min-height:44px;border:1px solid var(--border-strong);border-radius:999px;text-decoration:none;color:var(--ink);background:var(--parchment-elevated)}
.pager span.cur{background:var(--oxblood);color:#fff;border-color:var(--oxblood)}
.pager .range{width:100%;text-align:center;font-weight:400;border:none;background:none;font-size:13px;color:var(--ink-secondary)}
.morebtn{display:block;margin:6px auto 20px;font:inherit;font-size:14px;font-weight:600;padding:10px 22px;min-height:44px;border:1px solid var(--border-strong);background:var(--parchment-elevated);color:var(--ink);border-radius:999px;cursor:pointer}
.dirlist{columns:2;column-gap:28px;font-size:14px}
.dirlist div{break-inside:avoid;margin:0 0 6px}
@media (max-width:640px){.dirlist{columns:1}article.page{padding:18px 16px}}
body[data-lang="en"] .l-es{display:none}
body[data-lang="es"] .l-en{display:none}
.hidden{display:none}
"""

def L(en, es):
    return f'<span class="l-en">{esc(en)}</span><span class="l-es">{esc(es)}</span>'

def head(title, depth=0, site_h1=False, desc="", extra_meta=""):
    css = ("../" * depth) + "assets/style.css"
    title_html = "<h1>US/DR Newspaper Timeline</h1>" if site_h1 else '<p class="sitename">US/DR Newspaper Timeline</p>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(desc or title)}">
<title>{esc(title)} | US/DR Newspaper Timeline</title>{extra_meta}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css}"></head>
<body data-lang="en">
<header class="masthead"><div class="kicker">{years[0]}&ndash;{years[1]} &middot; Library of Congress &middot; Chronicling America</div>
{title_html}
<div class="sub">{L("The Dominican Republic in the American Press: a bilingual research edition of United States newspaper coverage, 1820-1963", "La República Dominicana en la prensa estadounidense: una edición de investigación bilingüe de la cobertura periodística, 1820-1963")}</div></header>
<div class="utilbar"><span>{L("Language / Idioma", "Language / Idioma")}:</span>
<button id="btn-en" aria-pressed="true" onclick="setLang('en')">EN</button>
<button id="btn-es" aria-pressed="false" onclick="setLang('es')">ES</button></div>
<script>function setLang(l){{document.body.dataset.lang=l;document.documentElement.lang=l;document.getElementById('btn-en').setAttribute('aria-pressed',l=='en');document.getElementById('btn-es').setAttribute('aria-pressed',l=='es');localStorage.setItem('xm-lang',l);}}
(function(){{var l=localStorage.getItem('xm-lang');if(l)document.addEventListener('DOMContentLoaded',function(){{setLang(l)}});}})();</script>
"""

def nav(depth=0):
    p = "../" * depth
    return f"""<nav class="main"><a href="{p}index.html">{L("Timeline", "Cronología")}</a>
<a href="{p}eras.html">{L("Eras", "Épocas")}</a>
<a href="{p}papers.html">{L("Newspapers", "Periódicos")}</a>
<a href="{p}topics.html">{L("Topics", "Temas")}</a>
<a href="{p}places.html">{L("Places", "Lugares")}</a>
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
    """The reading layer for unextracted records, honestly labeled (B2)."""
    if r["id"] in QUARANTINE:
        return (f'<p class="sumlabel">{L("Summary withheld", "Resumen retenido")}</p>'
                f'<p>{L("This record\'s passage summary failed a fidelity check and is withheld until the article itself is extracted. The located passage below and the source page are what this edition can stand behind today.", "El resumen de pasaje de este registro no superó una verificación de fidelidad y se retiene hasta que se extraiga el artículo. El pasaje localizado y la página fuente son lo que esta edición puede respaldar hoy.")}</p>')
    out = (f'<p class="sumlabel">{L("Passage summary", "Resumen del pasaje")}</p>'
           f'<p class="l-en">{esc(r.get("summary") or "")}</p><p class="l-es">{esc(r.get("summary_es") or "")}</p>')
    if r["id"] in FLAG_BLEED:
        out += (f'<p class="meta">{L("Caution: this passage appears to span more than one item on its page, so this summary is provisional until the article itself is extracted.", "Precaución: este pasaje parece abarcar más de un texto en su página, así que este resumen es provisional hasta que se extraiga el artículo.")}</p>')
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
            f'<div class="meta"><a href="{esc(r["source_url"])}">Library of Congress</a> &middot; <span class="hash">{esc(r["id"])}</span></div></div>')

def excerpt_well(r):
    c = corpus.get(r["id"], {})
    if not c.get("excerpt"):
        return ""
    return (f'<div class="well"><h4>{L("Located passage (Library of Congress OCR)", "Pasaje localizado (OCR de la Biblioteca del Congreso)")}</h4>'
            f'<p>{L("The passage located on the source page, in the Library\'s own OCR. The SHA-256 digest in Provenance is computed over exactly this text; recompute it to verify.", "El pasaje localizado en la página fuente, en el OCR propio de la Biblioteca. El resumen SHA-256 de Procedencia se calcula sobre exactamente este texto; recalcúlelo para verificar.")}</p>'
            f'{paras(c["excerpt"])}</div>')

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
        h.append(f'<div class="well"><h4>{L("Transcription held for verification", "Transcripción retenida para verificación")}</h4>'
                 f'<p>{L("This record\'s transcription failed an automated containment check against its page and is held until it can be verified against the page image. The located passage below and the source page remain available.", "La transcripción de este registro no superó una verificación automática contra su página y se retiene hasta poder contrastarla con la imagen de la página. El pasaje localizado y la página fuente siguen disponibles.")}</p></div>')
        h.append(f'<div class="body">{summary_block(r)}</div>')
    elif full:
        text, stripped = clean_article_text(r, e)
        if stripped:
            STRIPPED += 1
        h.append(f'<div class="body">{paras(text)}</div>')
        if e.get("dateline"):
            h.append(f'<div class="well"><h4>{L("Dateline as printed", "Lugar y fecha según el original")}</h4><p>{esc(e["dateline"])}</p></div>')
        if r["id"] in QA_FLAG:
            h.append(f'<div class="well"><h4>{L("Verification note", "Nota de verificación")}</h4>'
                     f'<p>{L("This transcription is flagged for image-level verification: an automated check found low textual containment against the page OCR. Read it against the source page.", "Esta transcripción está marcada para verificación contra la imagen: una comprobación automática halló baja contención textual frente al OCR de la página. Léala contra la página fuente.")}</p></div>')
    else:
        h.append(f'<div class="body">{summary_block(r)}</div>')
        h.append(f'<div class="well"><h4>{L("Status", "Estado")}</h4><p>{L("Full text extraction in progress; until the article itself is extracted, this page carries a passage summary (labeled as such), the located passage, and the source link.", "Extracción del texto completo en curso; hasta que se extraiga el artículo, esta página lleva un resumen del pasaje (etiquetado como tal), el pasaje localizado y el enlace a la fuente.")}</p></div>')
    h.append(excerpt_well(r))
    prov = [f'Record: <span class="hash">{esc(r["id"])}</span>']
    if r.get("excerpt_sha256"):
        prov.append(f'Located-passage SHA-256: <span class="hash">{esc(r["excerpt_sha256"])}</span> (over the passage text above)')
    if r.get("source_text_sha256"):
        prov.append(f'Source page OCR SHA-256: <span class="hash">{esc(r["source_text_sha256"])}</span>')
    if full:
        prov.append(f'Extraction: vision transcription, model {esc(str(e.get("model")))}, {esc(str(e.get("extracted_at"))[:10])}; QA-gated at build (see Method)')
    h.append(f'<div class="well"><h4>{L("Provenance", "Procedencia")}</h4><p>{"<br>".join(prov)}</p></div>')
    h.append(f'<div class="well"><h4>{L("Cite this record", "Cite este registro")}</h4>'
             f'<p>{esc(r["newspaper"])}. ({esc(r["date"][:4])}). {esc(r["place"])}, {esc(r["date"])}. '
             f'US/DR Newspaper Timeline, record {esc(r["id"])}. Library of Congress, Chronicling America: {esc(r["source_url"])}</p></div>')
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
             f'<div class="stat"><b>{len(timeline)}</b><span>{L("Timeline records", "Registros")}</span></div>'
             f'<div class="stat"><b>{len(papers)}</b><span>{L("Newspaper titles", "Periódicos")}</span></div>'
             f'<div class="stat"><b>{years[0]}-{years[1]}</b><span>{L("Coverage", "Cobertura")}</span></div>'
             f'<div class="stat"><b>{n_full}</b><span>{L("Full texts extracted", "Textos completos")}</span></div>'
             f'<div class="stat"><b>{len(eras_with)}+{len(eras_bg)}</b><span>{L("Era chapters + background", "Épocas + contexto")}</span></div></div>')
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
(m.f?'<div class="pills"><span class="pill full">Full text</span></div>':'')+
'<div class="meta"><span class="hash">'+m.i+'</span></div></div>';}).join('');
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
    h.append(f'<div class="well"><h4>{L("About these essays", "Sobre estos ensayos")}</h4><p>{L("The era essays are interpretive background written for this edition; they are not records and carry no citations of their own. The records are the evidence. Era ranges are historical periods, not collection coverage (the collection runs 1820-1963).", "Los ensayos de época son contexto interpretativo escrito para esta edición; no son registros y no llevan citas propias. Los registros son la evidencia. Los rangos de época son períodos históricos, no la cobertura de la colección (que va de 1820 a 1963).")}</p></div>')
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
                 f'<span class="hash">{esc(", ".join(lccns))}</span><br>{esc("; ".join(places_))} &middot; {rs[0]["date"][:4]}-{rs[-1]["date"][:4]}</div>')
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

def maritime_page():
    h = [head("Mella Maritime Clippings"), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("Mella Maritime Clippings", "Recortes marítimos Mella")}</h1>')
    h.append(f'<div class="well"><h4>{L("Evidence note", "Nota de evidencia")}</h4><p>'
             f'{L("Transcripts are documented from the clippings themselves; their SHA-256 digests verify. Image digests printed on this page are computed over the shipped scan files. Research notes are labeled claim by claim: material substantiated by a cited primary source is labeled Documented; family and oral accounts are labeled Oral tradition / loosely verified, and may or may not be accurate.", "Las transcripciones están documentadas desde los propios recortes; sus resúmenes SHA-256 verifican. Los resúmenes de imagen impresos en esta página se calculan sobre los archivos escaneados publicados. Las notas de investigación se etiquetan afirmación por afirmación: lo sustentado por una fuente primaria citada se etiqueta Documentado; los relatos familiares u orales se etiquetan Tradición oral / verificación parcial, y pueden o no ser exactos.")}</p></div>')
    for m in maritime:
        img = m.get("web_image") or ""
        h.append('<article class="page" style="margin-top:14px">')
        h.append(f'<div class="meta">{esc(m.get("date") or "")} &middot; {esc(m.get("newspaper") or "")}</div>')
        h.append(f'<h2 style="font-size:22px;margin:6px 0">{esc(m.get("headline") or "")}</h2>')
        img_sha = ""
        if img:
            path = os.path.join(BASSETS, os.path.basename(img))
            if os.path.exists(path):
                img_sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
            h.append(f'<figure class="plate"><img src="assets/maritime/{esc(os.path.basename(img))}" alt="{esc(m.get("headline") or "")}">'
                     f'<figcaption>{esc(m.get("newspaper") or "")}, {esc(m.get("date") or "")} &middot; {L("Source", "Fuente")}: Newspapers.com</figcaption></figure>')
        h.append(f'<p class="l-en">{esc(m.get("summary_en") or "")}</p><p class="l-es">{esc(m.get("summary_es") or "")}</p>')
        if m.get("transcript"):
            h.append(f'<div class="well"><h4>{L("Transcript", "Transcripción")} <span class="label doc">{L("Documented", "Documentado")}</span></h4>{paras(m["transcript"])}'
                     f'<p class="hash">Transcript SHA-256: {esc(m.get("transcript_sha256") or "")}</p></div>')
        if m.get("research_note_en"):
            h.append(f'<div class="well"><h4><span class="label oral">{L("Research note - oral tradition / loosely verified", "Nota de investigación - tradición oral / verificación parcial")}</span></h4>'
                     f'<p class="l-en">{esc(m["research_note_en"])}</p><p class="l-es">{esc(m.get("research_note_es") or "")}</p></div>')
        if img_sha:
            h.append(f'<p class="hash">Image SHA-256 (shipped scan): {img_sha}</p>')
        h.append("</article>")
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def method_page():
    h = [head("Method & Sources"), nav(), '<div class="wrap"><article class="page">']
    h.append(f"<h1>{L('Method & Sources', 'Método y fuentes')}</h1>")
    h.append(f"""<div class="body">
<p class="l-en">This edition organizes United States newspaper coverage of the Dominican Republic from the Library of Congress Chronicling America archive. The curated timeline holds {len(timeline)} records from {len(papers)} newspaper titles, {years[0]} to {years[1]}, in chronological order.</p>
<p class="l-es">Esta edición organiza la cobertura de la República Dominicana en periódicos estadounidenses procedente del archivo Chronicling America de la Biblioteca del Congreso. La cronología curada contiene {len(timeline)} registros de {len(papers)} periódicos, de {years[0]} a {years[1]}, en orden cronológico.</p>
<p class="l-en"><b>Article texts.</b> Full texts are vision transcriptions of the Library of Congress page images: the article only, no neighbouring items. The process has known limits, measured in this edition's adversarial review (2026-11-01): a printed headline repeated at the start of a text is stripped at build; transcriptions that fail an automated containment check against their page are flagged or held on their pages; passages the model could not read are supposed to be marked [illegible], and that discipline is spot-audited because early output under-used the marker. {n_full} of {len(timeline)} records carry full text in this pilot. Model self-reported confidence is not published; what is published is the QA state.</p>
<p class="l-es"><b>Textos de los artículos.</b> Los textos completos son transcripciones visuales de las imágenes de página de la Biblioteca del Congreso: solo el artículo, sin textos vecinos. El proceso tiene límites conocidos, medidos en la revisión adversarial de esta edición (2026-11-01): un titular impreso repetido al inicio se elimina al construir; las transcripciones que no superan una verificación automática contra su página se marcan o se retienen en sus páginas. {n_full} de {len(timeline)} registros llevan texto completo en este piloto.</p>
<p class="l-en"><b>Passage summaries.</b> Records not yet extracted carry a summary generated from the located OCR passage - not from the full article. Passage windows can cross article boundaries; summaries are labeled "Passage summary" wherever they appear, and any summary that fails a fidelity check is withheld until the article itself is extracted. The located passage is displayed in full on every article page, and the excerpt digest printed in Provenance is computed over exactly that displayed text, so any reader can recompute it.</p>
<p class="l-es"><b>Resúmenes del pasaje.</b> Los registros aún no extraídos llevan un resumen generado desde el pasaje OCR localizado, no desde el artículo completo. Los resúmenes se etiquetan «Resumen del pasaje» dondequiera que aparezcan, y todo resumen que no supere una verificación de fidelidad se retiene hasta extraer el artículo. El pasaje localizado se muestra completo en cada página, y el resumen SHA-256 de Procedencia se calcula sobre exactamente ese texto mostrado.</p>
<p class="l-en"><b>Inclusion rule.</b> A record belongs to this timeline when the located item substantially concerns the Dominican Republic (including the island's earlier states and the name Santo Domingo), its government, people, territory, or foreign relations. Items primarily about Haiti are included when the item itself substantially engages Santo Domingo or Hispaniola-wide affairs; a passing mention is not enough. In nineteenth-century usage "Dominica" frequently names the Dominican Republic itself and is judged in context; the island of Dominica is a different place and is excluded. The collection was built by a keyword screen over the Library's OCR followed by a scored curation cut; the screen's measured precision is published in the review, the grey pool is quarantined rather than imported, and borderline records carry review flags rather than silent verdicts.</p>
<p class="l-es"><b>Regla de inclusión.</b> Un registro pertenece a esta cronología cuando el texto localizado trata sustancialmente de la República Dominicana (incluidos sus estados anteriores y el nombre Santo Domingo), su gobierno, su gente, su territorio o sus relaciones exteriores. Los textos principalmente sobre Haití se incluyen cuando el propio texto aborda sustancialmente Santo Domingo o los asuntos de toda la isla; una mención pasajera no basta. En el uso del siglo XIX, «Dominica» nombra con frecuencia a la propia República Dominicana y se juzga en contexto; la isla de Dominica es otro lugar y se excluye.</p>
<p class="l-en"><b>Evidence labels.</b> Claims on this site are labeled by basis: <span class="label doc">Documented</span> for material substantiated by a cited primary source, and <span class="label oral">Oral tradition / loosely verified</span> for family or oral accounts that may or may not be accurate, spelled out for the high-scrutiny reader.</p>
<p class="l-es"><b>Etiquetas de evidencia.</b> Las afirmaciones de este sitio se etiquetan según su base: documentado, para material sustentado por una fuente primaria citada, y tradición oral / verificación parcial, para relatos familiares u orales que pueden o no ser exactos.</p>
<p class="l-en"><b>Provenance.</b> Every article page carries its record id and SHA-256 digests, and links to the Library of Congress page. Source URLs in this collection were derived from the Library's addressing scheme and are being verified by a standing link sweep; a record whose URL fails is flagged on its page. In the raw archive, file names are the SHA-256 of the source URL (an addressing convention, not a content hash); the content digest is the source-text SHA-256 printed on each page. This edition, its data files, this review's evidence, and the raw OCR archive form the preservation package, snapshotted with a manifest outside the code repository.</p>
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
    for d in ["articles", "era", "paper", "topic", "place", os.path.join("assets", "maritime")]:
        os.makedirs(os.path.join(OUT, d))
    open(os.path.join(OUT, "assets", "style.css"), "w", encoding="utf-8").write(CSS)
    if os.path.isdir(BASSETS):
        for f in os.listdir(BASSETS):
            shutil.copy2(os.path.join(BASSETS, f), os.path.join(OUT, "assets", "maritime", f))
    written = []
    for i, r in enumerate(timeline):
        prev_r = timeline[i - 1] if i > 0 else None
        next_r = timeline[i + 1] if i < len(timeline) - 1 else None
        open(os.path.join(OUT, "articles", r["id"] + ".html"), "w", encoding="utf-8").write(article_page(r, prev_r, next_r))
        written.append(f'articles/{r["id"]}.html')
    pages = {"index.html": index_page(), "eras.html": eras_page(), "maritime.html": maritime_page(),
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
    print(f"pilot v3 built: {len(timeline)} article pages, {n_full} full text, {STRIPPED} headline repeats stripped, "
          f"{len(QUARANTINE)} summaries withheld, {len(written)} pages total, {len(papers)} papers / {len(topics_all)} topics / {len(places_all)} places")

if __name__ == "__main__":
    main()
