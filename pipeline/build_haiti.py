#!/usr/bin/env python3
"""Build the "Haiti in the American Press" section - a sibling collection
under the US/DR Newspaper Timeline branch, at pilot-site/haiti/.

PiK0's ruling (2026-11-01): "Haiti: BUILD IT" - the 5,346-record Haiti-only
finding from the deep dig becomes its own collection, from the staged set
in data/haiti-staging.jsonl (6,184 records after the wide screen).

The screen, in the section's own words: records whose archive search terms
include Haiti, Hayti, Port-au-Prince or Saint-Domingue, excluding records
carrying Dominican-substance signals and excluding anything already in the
main timeline. Span 1822-1964.

Same rules as the main site (build_v5.py), non-negotiable:
- same stylesheet (../assets/style.css), same tokens/components, no new
  colors; Book Cover masthead adapted to the section title.
- complete bilingual chrome from one string table (en+es), Spanish
  default, same flag/theme toggles; attributes carry plain text only.
- topics pass through v5's TOPIC_MERGE into TOPIC_LABELS; an unmapped
  key FAILS the build; pills are links with human labels.
- NO invented summaries. Records are passage-backed: the article page
  presents the passage honestly labeled, plus newspaper/date/place,
  citation, Library of Congress link, observation box.
- the build ends with gates and exits nonzero on any failure.

Reuse is exact by construction: TOPIC_MERGE, TOPIC_LABELS, STR, CSS,
the flag SVGs and MONTHS are read out of build_v5.py's source with ast
literal evaluation (the v5 module itself is never executed here).

Output: ~/workspace/chronicling-america/pilot-site/haiti/ (static, local
only - nothing is pushed by this script).
"""
import ast, json, os, re, shutil, sys
from html import escape as esc, unescape
from datetime import date as _date

BASE = os.path.expanduser("~/workspace/chronicling-america")
OUT = os.path.join(BASE, "pilot-site")
HOUT = os.path.join(OUT, "haiti")
STAGING = os.path.join(BASE, "data/haiti-staging.jsonl")
V5_SRC = os.path.join(BASE, "scripts/build_v5.py")
PAGE_SIZE = 100
SITE_BASE = "https://xmella.me/us-dr-newspaper-timeline/"

# ------------------------------------------------- exact reuse from v5
def _extract_v5(names):
    tree = ast.parse(open(V5_SRC, encoding="utf-8").read())
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in names:
            found[node.targets[0].id] = ast.literal_eval(node.value)
    missing = names - set(found)
    if missing:
        print(f"BUILD FAILED: could not extract {sorted(missing)} from build_v5.py")
        sys.exit(1)
    return found

_v5 = _extract_v5({"TOPIC_MERGE", "TOPIC_LABELS", "STR", "CSS",
                   "FLAG_ES", "FLAG_GB", "MONTHS"})
TOPIC_MERGE = _v5["TOPIC_MERGE"]
TOPIC_LABELS = _v5["TOPIC_LABELS"]
CSS = _v5["CSS"]            # not written out (the section links v5's file);
                            # extracted so a drift in v5 is visible here
FLAG_ES = _v5["FLAG_ES"]
FLAG_GB = _v5["FLAG_GB"]
MONTHS = _v5["MONTHS"]
STR = dict(_v5["STR"])

# ------------------------------------------------------- Haiti strings
# Overrides and additions on top of v5's table. Shared keys keep v5's
# exact wording; section keys are new. Gate 3 checks every key used.
STR.update({
    "section_title": ("Haiti in the American Press",
                      "Haití en la prensa estadounidense"),
    "site_sub": ("A companion to the main timeline: the same American newspapers, turned toward Haiti itself — its ports and presidents, its sugar and its storms — in English and Spanish.",
                 "Una compañera de la cronología principal: los mismos periódicos estadounidenses, vueltos hacia Haití mismo — sus puertos y sus presidentes, su azúcar y sus tormentas — en inglés y en español."),
    "meta_desc_haiti": ("A bilingual companion collection of United States newspaper coverage of Haiti, {y0} to {y1}: {n} articles from {p} newspapers, gathered from the same Library of Congress archive as the US/DR Newspaper Timeline.",
                        "Una colección bilingüe compañera de la cobertura de Haití en los periódicos de Estados Unidos, de {y0} a {y1}: {n} artículos de {p} periódicos, reunidos del mismo archivo de la Biblioteca del Congreso que la Cronología EE. UU./RD."),
    "nav_main_timeline": ("Main timeline", "Cronología principal"),
    "nav_haiti": ("Haiti", "Haití"),
    "nav_decades": ("Decades", "Décadas"),
    "decades_h1": ("Browse by decade", "Explorar por década"),
    "browse_decade_link": ("Browse this decade", "Ver esta década"),
    "stat_decades": ("Decades", "Décadas"),
    "filter_decade_aria": ("Filter by decade", "Filtrar por década"),
    "all_decades": ("All decades", "Todas las décadas"),
    "search_ph": ("Search papers, places, passages",
                  "Buscar periódicos, lugares, pasajes"),
    "search_aria": ("Search the Haiti collection",
                    "Buscar en la colección de Haití"),
    "search_hint": ("Search this collection (accents optional), filter by decade or topic, or browse below. Results appear 50 at a time.",
                    "Busque en esta colección (acentos opcionales), filtre por década o tema, o explore más abajo. Los resultados aparecen de 50 en 50."),
    "intro_haiti_p1": ("The same American newspapers that followed the Dominican Republic also followed Haiti — closely, and for just as long. This companion collection gathers that coverage on its own: revolutions and recognitions, sugar and debt, gunboats and hurricanes, and the everyday traffic between Haitian ports and American ones. What is here is Haiti itself, in the order the papers printed it. Pieces mainly about the Dominican Republic live in the main timeline.",
                       "Los mismos periódicos estadounidenses que siguieron a la República Dominicana también siguieron a Haití — de cerca, y durante el mismo tiempo. Esta colección compañera reúne esa cobertura por su cuenta: revoluciones y reconocimientos, azúcar y deudas, cañoneras y huracanes, y el tráfico cotidiano entre los puertos haitianos y los estadounidenses. Lo que hay aquí es Haití mismo, en el orden en que los periódicos lo imprimieron. Las piezas principalmente sobre la República Dominicana están en la cronología principal."),
    "intro_haiti_p2": ("How it was gathered, in plain words: the Library of Congress's newspaper archive was searched for the names the papers themselves used for the country — Haiti, Hayti, Port-au-Prince, Saint-Domingue — and the pieces that take up Haiti in earnest were kept. Each page here carries the passage found on the newspaper page, copied with its reading errors and all; the original page is always one click away.",
                       "Cómo se reunió, en palabras llanas: se buscó en el archivo de periódicos de la Biblioteca del Congreso los nombres que los propios periódicos usaban para el país — Haiti, Hayti, Port-au-Prince, Saint-Domingue — y se guardaron las piezas que tratan a Haití en serio. Cada página aquí lleva el pasaje encontrado en la página del periódico, copiado con sus errores de lectura y todo; la página original está siempre a un clic."),
    "footer_line_haiti": ("Part of the US/DR Newspaper Timeline, from the Library of Congress's Chronicling America archive. Observations and corrections are welcome:",
                          "Parte de la Cronología EE. UU./República Dominicana, del archivo Chronicling America de la Biblioteca del Congreso. Observaciones y correcciones son bienvenidas:"),
    "decade_count_line": ("{n} articles in this collection from this decade",
                          "{n} artículos de esta colección de esta década"),
    "haiti_status_p": ("This article's passage has not been located yet. The newspaper, its date, and the link to the original page are here; the passage will join them when it is read.",
                       "El pasaje de este artículo aún no se ha localizado. El periódico, su fecha y el enlace a la página original están aquí; el pasaje se sumará cuando se lea."),
    "papers_intro_haiti": ("Every newspaper title in this collection, with its Library of Congress Control Number (LCCN) where the archive gives one, its publication places, and how many of its pieces are here.",
                           "Cada periódico de esta colección, con su número de control de la Biblioteca del Congreso (LCCN) cuando el archivo lo da, sus lugares de publicación y cuántas de sus piezas están aquí."),
    "topics_intro_haiti": ("Every subject this collection is organized by. Pick one and follow it through the years.",
                           "Cada tema que organiza esta colección. Elija uno y sígalo a través de los años."),
    "main_timeline_note": ("Pieces mainly about the Dominican Republic live in the main timeline.",
                           "Las piezas principalmente sobre la República Dominicana están en la cronología principal."),
})

def ST(key, lang):
    return STR[key][0] if lang == "en" else STR[key][1]

def L(key, **fmt):
    en, es = STR[key]
    if fmt:
        en, es = en.format(**fmt), es.format(**fmt)
    return f'<span class="l-en">{esc(en)}</span><span class="l-es">{esc(es)}</span>'

def Lp(en, es):
    return f'<span class="l-en">{esc(en)}</span><span class="l-es">{esc(es)}</span>'

def A(attr, key, **fmt):
    """Language-dependent attribute: plain text only, swapped by the
    toggle script from data-en/data-es. NEVER markup."""
    en, es = STR[key]
    if fmt:
        en, es = en.format(**fmt), es.format(**fmt)
    return (f'{attr}="{esc(es)}" data-en="{esc(en)}" data-es="{esc(es)}" '
            f'data-attr="{attr}"')

def AO(key):
    en, es = STR[key]
    return f'data-en="{esc(en)}" data-es="{esc(es)}" data-attr="text"'

def fmt_date(iso):
    try:
        y, m, d = (int(x) for x in (iso or "")[:10].split("-"))
        _date(y, m, d)
        en = f"{MONTHS['en'][m - 1]} {d}, {y}"
        es = f"{d} de {MONTHS['es'][m - 1]} de {y}"
        return Lp(en, es)
    except Exception:
        return esc(iso or "")

# ------------------------------------------------------------------ data
def load_jsonl(p):
    rows = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

def norm_topics(keys):
    out = []
    for k in keys or []:
        nk = TOPIC_MERGE.get(k, k)
        if nk not in out:
            out.append(nk)
    return out

records = []
for r in load_jsonl(STAGING):
    records.append({
        "id": r["record_id"], "date": r.get("publication_date") or "",
        "year": r.get("year"), "newspaper": r.get("newspaper") or "",
        "place": r.get("place") or "", "source_url": r.get("source_url") or "",
        "lccn": r.get("lccn") or "",
        "topics": norm_topics(r.get("topics")),
        "passage": r.get("excerpt") or "",
        "cluster_id": r.get("cluster_id") or "",
        "cluster_size": r.get("cluster_size") or 1,
        "np": r["record_id"].startswith("np"),
    })
records.sort(key=lambda r: (r["date"], r["id"]))
by_id = {r["id"]: r for r in records}

def decade_of(r):
    y = r["year"] or int((r["date"] or "0")[:4])
    return (y // 10) * 10

for r in records:
    r["decade"] = decade_of(r)

def decade_pair(d):
    return Lp(f"{d}s", f"Años {d}")

papers = sorted({r["newspaper"] for r in records})
years = (records[0]["date"][:4], records[-1]["date"][:4])
topics_all = sorted({t for r in records for t in r["topics"]})
decades_all = sorted({r["decade"] for r in records})

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

paper_slug = unique_slugs(papers)
topic_slug = unique_slugs(topics_all)
decade_slug = {d: f"{d}s" for d in decades_all}
paper_records = {p: [r for r in records if r["newspaper"] == p] for p in papers}
topic_records = {t: [r for r in records if t in r["topics"]] for t in topics_all}
decade_records = {d: [r for r in records if r["decade"] == d] for d in decades_all}

# reprint clusters, staged members only
by_cluster = {}
for r in records:
    if r["cluster_id"]:
        by_cluster.setdefault(r["cluster_id"], []).append(r["id"])
cluster_siblings = {}
for r in records:
    if r["cluster_id"]:
        sibs = [i for i in by_cluster[r["cluster_id"]] if i != r["id"]]
        if sibs:
            cluster_siblings[r["id"]] = sorted(sibs, key=lambda i: (by_id[i]["date"], i))

def npages(rs):
    return max(1, (len(rs) + PAGE_SIZE - 1) // PAGE_SIZE)

def lead_of(r, n=200):
    return re.sub(r"\s+", " ", r["passage"]).strip()[:n]

# ------------------------------------------------------------- page chrome
# root: "" for pages at the section root (haiti/), "../" for pages one
# level down (haiti/articles/, haiti/topic/, ...). The stylesheet lives
# at the branch root: root + "../assets/style.css".
def head(title_txt, root="", site_h1=False, desc_es=""):
    css = root + "../assets/style.css"
    title_html = (f"<h1>{L('section_title')}</h1>" if site_h1
                  else f'<p class="sitename">{L("section_title")}</p>')
    if not desc_es:
        desc_es = ST("meta_desc_haiti", "es").format(y0=years[0], y1=years[1],
                                                     n=len(records), p=len(papers))
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(desc_es)}">
<title>{esc(title_txt)} | {esc(ST("section_title", "es"))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{css}"></head>
<body data-lang="es" data-theme="light">
<script>(function(){{var l=localStorage.getItem('xm-lang');if(l){{document.body.dataset.lang=l;document.documentElement.lang=l;}}
var t=localStorage.getItem('xm-theme');if(!t&&window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches)t='dark';
if(t)document.body.dataset.theme=t;}})();</script>
<header class="masthead"><div class="frame"><div class="kicker">{years[0]}&ndash;{years[1]} &middot; {L("kicker_loc")} &middot; Chronicling America</div>
{title_html}
<div class="sub">{L("site_sub")}</div></div></header>
<div class="utilbar">
<button id="btn-es" aria-pressed="true" onclick="setLang('es')">{FLAG_ES} Español</button>
<button id="btn-en" aria-pressed="false" onclick="setLang('en')">{FLAG_GB} English</button>
<span class="sep"></span>
<button id="btn-theme" aria-pressed="false" onclick="toggleTheme()">{L("theme_dark")} / {L("theme_light")}</button></div>
<script>function swapAttrs(l){{document.querySelectorAll('[data-attr]').forEach(function(el){{var a=el.getAttribute('data-attr'),v=el.getAttribute('data-'+l);if(v===null)return;if(a==='text'){{el.textContent=v;}}else{{el.setAttribute(a,v);}}}});}}
function setLang(l){{document.body.dataset.lang=l;document.documentElement.lang=l;document.getElementById('btn-en').setAttribute('aria-pressed',l=='en');document.getElementById('btn-es').setAttribute('aria-pressed',l=='es');swapAttrs(l);localStorage.setItem('xm-lang',l);if(window.__onLang)window.__onLang(l);}}
function toggleTheme(){{var d=document.body.dataset.theme=='dark'?'light':'dark';document.body.dataset.theme=d;document.getElementById('btn-theme').setAttribute('aria-pressed',d=='dark');localStorage.setItem('xm-theme',d);}}
(function(){{document.addEventListener('DOMContentLoaded',function(){{setLang(document.body.dataset.lang);
document.getElementById('btn-theme').setAttribute('aria-pressed',document.body.dataset.theme=='dark');}});}})();</script>
"""

def nav(root=""):
    return (f'<nav class="main"><a href="{root}../index.html">{L("nav_main_timeline")}</a>\n'
            f'<a href="{root}index.html">{L("nav_haiti")}</a>\n'
            f'<a href="{root}decades.html">{L("nav_decades")}</a>\n'
            f'<a href="{root}papers.html">{L("nav_papers")}</a>\n'
            f'<a href="{root}topics.html">{L("nav_topics")}</a></nav>')

def foot():
    return (f"""<footer><div class="frame">{L("section_title")} &middot; US/DR Newspaper Timeline &middot; xmella.me<br>
{L("footer_line_haiti")} <a href="mailto:admin@xmella.me">admin@xmella.me</a></div></footer>
</body></html>""")

# -------------------------------------------------------------- components
def paras(text):
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)

def topic_label_pair(key):
    en, es = TOPIC_LABELS[key]
    return Lp(en, es)

def topic_pills(r, root=""):
    return "".join(
        f'<a class="pill" href="{root}topic/{topic_slug[t]}-1.html">{topic_label_pair(t)}</a>'
        for t in r["topics"])

def meta_line(r):
    bits = [fmt_date(r["date"])]
    if r["place"]:
        bits.append(esc(r["place"]))
    bits.append(decade_pair(r["decade"]))
    return " &middot; ".join(bits)

def card(r, root=""):
    lead = lead_of(r, 200)
    body = f'<p class="sumlabel">{L("passage_label")}</p><p>{esc(lead)}&hellip;</p>' if lead else ""
    if r["source_url"]:
        src = f'<div class="meta"><a href="{esc(r["source_url"])}">{L("see_original")}</a></div>'
    elif r["np"]:
        src = f'<div class="meta">{L("np_credit")}</div>'
    else:
        src = ""
    return (f'<div class="card"><div class="meta">{meta_line(r)}</div>'
            f'<h3><a href="{root}articles/{esc(r["id"])}.html">{esc(r["newspaper"])}</a></h3>'
            f'{body}<div class="pills">{topic_pills(r, root)}</div>{src}</div>')

def observe_box(r, page_path):
    from urllib.parse import quote
    subj = quote(f'Observation: {r["newspaper"]}, {r["date"]}')
    body = quote(f'{r["newspaper"]} ({r["date"]})\n{SITE_BASE}{page_path}\n\n')
    return (f'<div class="observe"><div class="inner"><h4>{L("observe_h")}</h4>'
            f'<p>{L("observe_p")}</p>'
            f'<a class="btn" href="mailto:admin@xmella.me?subject={subj}&body={body}">{L("observe_btn")}</a>'
            f'</div></div>')

def context_plate(r, prev_r, next_r):
    h = [f'<div class="ctx"><h4>{L("context_h")}</h4>']
    n = len(decade_records[r["decade"]])
    h.append(f'<div class="era-line"><b>{decade_pair(r["decade"])}</b> &middot; '
             f'{Lp(ST("decade_count_line", "en").format(n=n), ST("decade_count_line", "es").format(n=n))}</div>')
    pn = []
    if prev_r:
        pn.append(f'<span>&larr; {L("earlier_article")}: <a href="{esc(prev_r["id"])}.html">{esc(prev_r["newspaper"])}</a> &middot; {fmt_date(prev_r["date"])}</span>')
    else:
        pn.append("<span></span>")
    if next_r:
        pn.append(f'<span>{L("later_article")}: <a href="{esc(next_r["id"])}.html">{esc(next_r["newspaper"])}</a> &middot; {fmt_date(next_r["date"])} &rarr;</span>')
    h.append(f'<div class="pn">{pn[0]}{pn[1] if len(pn) > 1 else ""}</div>')
    if r["topics"]:
        t = r["topics"][0]
        sibs = [x for x in topic_records[t] if x["id"] != r["id"]]
        if sibs:
            def daynum(x):
                try:
                    return _date(int(x["date"][:4]), int(x["date"][5:7]), int(x["date"][8:10])).toordinal()
                except Exception:
                    return 0
            base = daynum(r)
            sibs.sort(key=lambda x: (abs(daynum(x) - base), x["date"]))
            near = sorted(sibs[:3], key=lambda x: (x["date"], x["id"]))
            en_l, es_l = TOPIC_LABELS[t]
            h.append(f'<h4 style="margin-top:14px">{Lp(ST("more_on", "en").format(label=en_l), ST("more_on", "es").format(label=es_l))}</h4><ul>')
            for x in near:
                h.append(f'<li><a href="{esc(x["id"])}.html">{esc(x["newspaper"])}</a> &middot; {fmt_date(x["date"])}</li>')
            h.append("</ul>")
    h.append("</div>")
    return "".join(h)

def trails_plate(r, root="../"):
    sib_ids = cluster_siblings.get(r["id"])
    if not sib_ids:
        return ""
    h = [f'<div class="well"><h4>{L("also_ran_h")}</h4>']
    for sid in sib_ids:
        sib = by_id[sid]
        line = f'<a href="{root}articles/{esc(sid)}.html">{esc(sib["newspaper"])}</a>'
        if sib["place"]:
            line += f' &middot; {esc(sib["place"])}'
        line += f' &middot; {fmt_date(sib["date"])}'
        if sib["source_url"]:
            line += f' &middot; <a href="{esc(sib["source_url"])}">{L("see_original")}</a>'
        h.append(f"<p>{line}</p>")
    h.append("</div>")
    return "".join(h)

def article_page(r, prev_r, next_r):
    desc_es = (lead_of(r, 200) or f'{r["newspaper"]}, {r["date"]}')
    dc = [f'<meta name="DC.title" content="{esc(r["newspaper"])}">',
          f'<meta name="DC.publisher" content="{esc(r["newspaper"])}">',
          f'<meta name="DC.date" content="{esc(r["date"])}">']
    if r["source_url"]:
        dc.append(f'<meta name="DC.source" content="{esc(r["source_url"])}">')
    dc.append(f'<meta name="DC.identifier" content="{esc(r["id"])}">')
    h = [head(r["newspaper"], root="../", desc_es=desc_es), nav(root="../"),
         '<div class="wrap"><article class="page">']
    # head() has no extra_meta slot; DC tags ride in the description call
    h[0] = h[0].replace("</title>", '</title>' + "".join(dc))
    h.append(f'<div class="meta">{meta_line(r)}</div>')
    h.append(f'<h1>{esc(r["newspaper"])}</h1>')
    src_bits = [esc(r["newspaper"])]
    if r["place"]:
        src_bits.append(esc(r["place"]))
    src_bits.append(fmt_date(r["date"]))
    h.append(f'<div class="src">{L("source_label")}: {" &middot; ".join(src_bits)}')
    if r["source_url"]:
        h.append(f'<br><a href="{esc(r["source_url"])}">{esc(r["source_url"])}</a>')
    if r["np"]:
        h.append(f'<br>{L("np_credit")}')
    h.append("</div>")
    if r["topics"]:
        h.append(f'<div class="pills">{topic_pills(r, root="../")}</div>')
    h.append(context_plate(r, prev_r, next_r))
    if r["passage"].strip():
        h.append(f'<div class="well"><h4>{L("passage_h")}</h4><p>{L("passage_intro_only")}</p>'
                 f'{paras(r["passage"])}</div>')
    else:
        h.append(f'<div class="well"><h4>{L("status_h")}</h4><p>{L("haiti_status_p")}</p></div>')
    h.append(trails_plate(r))
    yr = esc(r["date"][:4])
    if r["source_url"]:
        cite = (f'{esc(r["newspaper"])}. ({yr}). {esc(r["place"])}, {esc(r["date"])}. '
                f'Haiti in the American Press. Library of Congress, Chronicling America: {esc(r["source_url"])}')
        refs = (f'<p>Library of Congress, Chronicling America: '
                f'<a href="{esc(r["source_url"])}">{esc(r["newspaper"])}, {esc(r["date"])}</a>.</p>')
    elif r["np"]:
        cite = (f'{esc(r["newspaper"])}. ({yr}). {esc(r["date"])}. '
                f'Haiti in the American Press. {ST("np_credit", "en")} / {ST("np_credit", "es")}.')
        refs = f'<p>{L("np_credit")}: {esc(r["newspaper"])}, {esc(r["date"])}.</p>'
    else:
        cite = f'{esc(r["newspaper"])}. ({yr}). {esc(r["date"])}. Haiti in the American Press.'
        refs = f'<p>{esc(r["newspaper"])}, {esc(r["date"])}.</p>'
    h.append(f'<div class="well"><h4>{L("cite_h")}</h4><p>{cite}</p></div>')
    h.append(f'<div class="well"><h4>{L("references_h")}</h4>{refs}</div>')
    h.append(observe_box(r, f'haiti/articles/{r["id"]}.html'))
    h.append("</article></div>")
    h.append(foot())
    return "".join(h)

# ------------------------------------------------------------ listing pages
def pager(base, k, npages_, chunk_first, chunk_last, total):
    lo = (k - 1) * PAGE_SIZE + 1
    hi = min(k * PAGE_SIZE, total)
    items = [f'<span class="range">{lo}&ndash;{hi} {L("of_word")} {total} &middot; '
             f'{fmt_date(chunk_first)} &ndash; {fmt_date(chunk_last)}</span>']
    if k > 1:
        items.append(f'<a href="{base}-{k - 1}.html">&larr; {L("pager_earlier")}</a>')
    for j in range(1, npages_ + 1):
        items.append(f'<span class="cur">{j}</span>' if j == k else f'<a href="{base}-{j}.html">{j}</a>')
    if k < npages_:
        items.append(f'<a href="{base}-{k + 1}.html">{L("pager_later")} &rarr;</a>')
    return f'<div class="pager">{"".join(items)}</div>'

def listing_pages(facet, base, title_txt, title_html, rs, crumb):
    """Paginated listings for one facet value; files under haiti/<facet>/."""
    out = {}
    npg = npages(rs)
    for k in range(1, npg + 1):
        chunk = rs[(k - 1) * PAGE_SIZE: k * PAGE_SIZE]
        h = [head(f"{title_txt} ({k}/{npg})", root="../"), nav(root="../"), '<div class="wrap">']
        h.append(f'<div class="meta" style="margin-top:18px">{crumb} &middot; {L("page_word")} {k} {L("of_word")} {npg}</div>')
        h.append(f"<h1>{title_html}</h1>")
        h.append(pager(base, k, npg, chunk[0]["date"], chunk[-1]["date"], len(rs)))
        h.append("".join(card(r, root="../") for r in chunk))
        h.append(pager(base, k, npg, chunk[0]["date"], chunk[-1]["date"], len(rs)))
        h.append("</div>")
        h.append(foot())
        out[f"haiti/{facet}/{base}-{k}.html"] = "".join(h)
    return out

# ------------------------------------------------------------- search index
def search_index():
    rows = []
    for r in records:
        lead = lead_of(r, 240)
        rows.append({"i": r["id"], "d": r["date"], "n": r["newspaper"], "p": r["place"],
                     "u": decade_slug[r["decade"]],
                     "de": f'{r["decade"]}s', "ds": f'Años {r["decade"]}',
                     "t": [topic_slug[t] for t in r["topics"]],
                     "k": r["topics"],
                     "te": [TOPIC_LABELS[t][0] for t in r["topics"]],
                     "ts": [TOPIC_LABELS[t][1] for t in r["topics"]],
                     "h": r["newspaper"], "s": lead, "x": lead})
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

SEARCH_JS = r"""
var q=document.getElementById('q'),dsel=document.getElementById('fd'),tsel=document.getElementById('ft'),
res=document.getElementById('results'),cnt=document.getElementById('count'),
more=document.getElementById('more'),IDX=null,matches=[],shown=0,active=false,STEP=50;
function escS(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function fold(s){return (s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');}
function fmtD(iso,lang){var p=(iso||'').split('-');if(p.length<3)return iso;
var M=PACK.months[lang]||PACK.months.en,y=+p[0],m=+p[1],d=+p[2];
return lang=='es'?(d+' de '+M[m-1]+' de '+y):(M[m-1]+' '+d+', '+y);}
function render(){var lang=document.body.dataset.lang||'es';
if(!active){cnt.textContent='';res.innerHTML='';more.classList.add('hidden');return;}
res.innerHTML=matches.slice(0,shown).map(function(m){
var pills=m.t.map(function(sl,j){return '<a class="pill" href="topic/'+sl+'-1.html">'+escS(lang=='es'?m.ts[j]:m.te[j])+'</a>';}).join('');
return '<div class="card"><div class="meta">'+escS(fmtD(m.d,lang))+' &middot; '+escS(m.p)+' &middot; '+escS(lang=='es'?m.ds:m.de)+'</div>'+
'<h3><a href="articles/'+m.i+'.html">'+escS(m.h)+'</a></h3>'+
'<p>'+escS(m.s)+'</p>'+
(pills?'<div class="pills">'+pills+'</div>':'')+'</div>';}).join('');
cnt.textContent=matches.length?PACK[lang].results_count.replace('{n}',matches.length).replace('{total}',IDX.length):PACK[lang].results_none;
more.classList.toggle('hidden',shown>=matches.length);}
function run(){if(!IDX)return;var toks=fold(q.value).split(/\s+/).filter(Boolean);
var df=dsel.value,tf=tsel.value;active=!!(toks.length||df||tf);
if(!active){matches=[];shown=0;render();return;}
matches=IDX.filter(function(m){if(df&&m.u!==df)return false;if(tf&&m.t.indexOf(tf)<0)return false;
if(!toks.length)return true;
var hay=fold(m.d+' '+m.n+' '+m.p+' '+m.de+' '+m.ds+' '+m.h+' '+m.s+' '+m.k.join(' ')+' '+m.te.join(' ')+' '+m.ts.join(' '));
return toks.every(function(t){return hay.indexOf(t)>-1;});});
shown=Math.min(STEP,matches.length);render();}
function load(){if(IDX){run();return;}
fetch('assets/search-index-haiti.json').then(function(r){return r.json();}).then(function(j){IDX=j;run();});}
function syncChips(){document.querySelectorAll('.chip').forEach(function(c){
c.setAttribute('aria-pressed',c.getAttribute('data-tslug')===tsel.value?'true':'false');});}
q.addEventListener('focus',load);q.addEventListener('input',function(){IDX?run():load();});
dsel.addEventListener('change',function(){IDX?run():load();});
tsel.addEventListener('change',function(){syncChips();IDX?run():load();});
document.querySelectorAll('.chip').forEach(function(c){c.addEventListener('click',function(){
tsel.value=(tsel.value===c.getAttribute('data-tslug'))?'':c.getAttribute('data-tslug');
syncChips();IDX?run():load();});});
more.addEventListener('click',function(){shown=Math.min(shown+STEP,matches.length);render();});
window.__onLang=function(){if(IDX)render();};
(function(){var prm=new URLSearchParams(location.search),t=prm.get('t'),d=prm.get('d');
if(t)tsel.value=t;if(d)dsel.value=d;if(t||d){syncChips();load();}})();
"""

def index_page():
    desc_es = ST("meta_desc_haiti", "es").format(y0=years[0], y1=years[1],
                                                 n=len(records), p=len(papers))
    h = [head(ST("section_title", "es"), site_h1=True, desc_es=desc_es), nav()]
    h.append('<div class="wrap">')
    h.append('<div class="stats">'
             f'<div class="stat"><b>{len(records)}</b><span>{L("stat_articles")}</span></div>'
             f'<div class="stat"><b>{len(papers)}</b><span>{L("stat_papers")}</span></div>'
             f'<div class="stat"><b>{years[0]}-{years[1]}</b><span>{L("stat_years")}</span></div>'
             f'<div class="stat"><b>{len(decades_all)}</b><span>{L("stat_decades")}</span></div></div>')
    h.append(f'<div class="card"><p>{L("intro_haiti_p1")}</p><p>{L("intro_haiti_p2")}</p></div>')
    dec_opts = [f'<option value="" {AO("all_decades")}>{esc(ST("all_decades", "es"))}</option>']
    for d in decades_all:
        dec_opts.append(f'<option value="{decade_slug[d]}" data-en="{d}s" data-es="Años {d}" data-attr="text">Años {d}</option>')
    topic_opts = [f'<option value="" {AO("all_topics")}>{esc(ST("all_topics", "es"))}</option>']
    for t in sorted(topics_all, key=lambda t: TOPIC_LABELS[t][0]):
        topic_opts.append(f'<option value="{topic_slug[t]}" data-en="{esc(TOPIC_LABELS[t][0])}" data-es="{esc(TOPIC_LABELS[t][1])}" data-attr="text">{esc(TOPIC_LABELS[t][1])}</option>')
    h.append(f"""<div class="controls">
<input type="search" id="q" {A("placeholder", "search_ph")} {A("aria-label", "search_aria")}>
<select id="fd" {A("aria-label", "filter_decade_aria")}>{''.join(dec_opts)}</select>
<select id="ft" {A("aria-label", "filter_topic_aria")}>{''.join(topic_opts)}</select>
</div>
<div class="meta">{L("search_hint")}</div>
<div class="meta" id="count" style="margin-top:6px"></div>
<div id="results" style="margin-top:12px"></div>
<button class="morebtn hidden" id="more">{L("show_more")}</button>""")
    chips = []
    for t in sorted(topics_all, key=lambda t: -len(topic_records[t])):
        chips.append(f'<button class="chip" data-tslug="{topic_slug[t]}" aria-pressed="false">{topic_label_pair(t)}</button>')
    h.append(f'<h2 style="margin-top:28px">{L("chips_h")}</h2><div class="chips">{"".join(chips)}</div>')
    h.append(f'<h2 style="margin-top:28px">{L("decades_h1")}</h2>')
    for d in decades_all:
        rs = decade_records[d]
        h.append(f'<div class="card"><div class="meta">{L("period_label")}: {d}&ndash;{d + 9} &middot; {len(rs)} {L("articles_word")} &middot; {npages(rs)} {L("pages_word")}</div>'
                 f'<h3><a href="decade/{decade_slug[d]}-1.html">{decade_pair(d)}</a></h3></div>')
    h.append(f'<h2 style="margin-top:28px">{L("browse_catalog_h")}</h2>')
    h.append(f'<div class="card"><p><a href="papers.html">{L("nav_papers")}</a> ({len(papers)}) &middot; '
             f'<a href="topics.html">{L("nav_topics")}</a> ({len(topics_all)}) &middot; '
             f'<a href="decades.html">{L("nav_decades")}</a> ({len(decades_all)})</p>'
             f'<p>{L("main_timeline_note")} <a href="../index.html">{L("nav_main_timeline")}</a></p></div>')
    pack = {"en": {"results_count": STR["results_count"][0], "results_none": STR["results_none"][0]},
            "es": {"results_count": STR["results_count"][1], "results_none": STR["results_none"][1]},
            "months": MONTHS}
    js = SEARCH_JS.replace("PACK", "window.PACK")
    h.append('</div>\n<script>window.PACK=' + json.dumps(pack, ensure_ascii=False) + ';</script>')
    h.append("<script>" + js + "</script>")
    h.append(foot())
    return "".join(h)

# ---------------------------------------------------------- directory pages
def decades_page():
    h = [head(ST("nav_decades", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("decades_h1")}</h1>')
    for d in decades_all:
        rs = decade_records[d]
        h.append(f'<div class="card"><div class="meta">{L("period_label")}: {d}&ndash;{d + 9} &middot; {len(rs)} {L("articles_word")} &middot; {npages(rs)} {L("pages_word")}</div>'
                 f'<h2 style="font-size:19px;margin:4px 0 6px"><a href="decade/{decade_slug[d]}-1.html">{decade_pair(d)}</a></h2>'
                 f'<a href="decade/{decade_slug[d]}-1.html">{L("browse_decade_link")}</a></div>')
    h.append("</div>")
    h.append(foot())
    return "".join(h)

def papers_page():
    h = [head(ST("nav_papers", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("papers_h1")}</h1>')
    h.append(f'<p>{L("papers_intro_haiti")}</p>')
    h.append('<div class="dirlist">')
    for p in papers:
        rs = paper_records[p]
        lccns = sorted({r["lccn"] for r in rs if r["lccn"]})
        places_ = sorted({r["place"] for r in rs if r["place"]})
        lccn_line = f'<span class="catnum">{L("lccn_label")} {esc(", ".join(lccns))}</span><br>' if lccns else ""
        h.append(f'<div><a href="paper/{paper_slug[p]}-1.html"><b>{esc(p)}</b></a> ({len(rs)})<br>'
                 f'{lccn_line}{esc("; ".join(places_))} &middot; {rs[0]["date"][:4]}-{rs[-1]["date"][:4]}</div>')
    h.append('</div></div>')
    h.append(foot())
    return "".join(h)

def topics_page():
    h = [head(ST("nav_topics", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("topics_h1")}</h1><p>{L("topics_intro_haiti")}</p><div class="dirlist">')
    for t in sorted(topics_all, key=lambda t: TOPIC_LABELS[t][0]):
        h.append(f'<div><a href="topic/{topic_slug[t]}-1.html"><b>{topic_label_pair(t)}</b></a> ({len(topic_records[t])})</div>')
    h.append('</div></div>')
    h.append(foot())
    return "".join(h)

# -------------------------------------------------------------------- gates
def run_gates(files):
    """The Haiti gates, mirroring v5's. Any failure fails the build."""
    failures = []
    # gate 3: every STR key and topic label has both languages; every
    # topic in the data is mapped (unmapped keys fail the build)
    for k, (en, es) in STR.items():
        if not (en or "").strip() or not (es or "").strip():
            failures.append(f"gate3: STR key '{k}' is missing a language")
    for k, (en, es) in TOPIC_LABELS.items():
        if not en.strip() or not es.strip():
            failures.append(f"gate3: topic '{k}' is missing a label")
    for t in topics_all:
        if t not in TOPIC_LABELS:
            failures.append(f"gate3: topic key '{t}' in the Haiti data has NO label (unmapped keys fail the build)")
    html_files = {p: c for p, c in files.items() if p.endswith(".html")}
    all_keys = set(TOPIC_LABELS) | set(TOPIC_MERGE)
    for path, content in sorted(html_files.items()):
        noscript = re.sub(r"<script.*?</script>", " ", content, flags=re.S)
        noscript = re.sub(r"<style.*?</style>", " ", noscript, flags=re.S)
        noscript = re.sub(r"<!--.*?-->", " ", noscript, flags=re.S)
        # gate 1: no '<' inside any attribute value
        for m in re.finditer(r"<[^<>]+>", noscript):
            for am in re.finditer(r'"([^"]*)"', m.group(0)):
                if "<" in am.group(1):
                    failures.append(f"gate1 {path}: '<' inside attribute value: {am.group(1)[:70]!r}")
                    break
        # gate 2: no raw topic key in visible text (two-tier, as v5:
        # underscore keys are forbidden everywhere; single-word keys are
        # checked on the taxonomy surfaces, since they are also ordinary
        # words that occur inside the passages themselves)
        vis = unescape(re.sub(r"<[^<>]+>", " ", noscript))
        for k in sorted(all_keys):
            if "_" in k and k in vis:
                failures.append(f"gate2 {path}: raw topic key '{k}' in visible text")
        surfaces = re.findall(r'class="pill[^"]*"[^>]*>(.*?)</', noscript) \
            + re.findall(r'class="chip"[^>]*>(.*?)</', noscript) \
            + re.findall(r"<h[123][^>]*>(.*?)</h[123]>", noscript, flags=re.S) \
            + re.findall(r"<option[^>]*>(.*?)</option>", noscript)
        surf_text = unescape(re.sub(r"<[^<>]+>", " ", " ".join(surfaces)))
        for k in sorted(all_keys):
            if k in surf_text:
                failures.append(f"gate2 {path}: raw topic key '{k}' rendered on a taxonomy surface")
        # gate 4: every relative href resolves - to a generated Haiti
        # file, or to a branch-root file that exists in pilot-site
        base_dir = os.path.dirname(path)
        for hm in re.finditer(r'href="([^"]*)"', noscript):
            href = hm.group(1)
            if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target:
                continue
            resolved = os.path.normpath(os.path.join(base_dir, target)).replace(os.sep, "/")
            if resolved not in files and not os.path.exists(os.path.join(OUT, resolved)):
                failures.append(f"gate4 {path}: dead internal link '{href}' -> '{resolved}'")
    # gate 5: search index rows == generated article pages
    idx = json.loads(files["haiti/assets/search-index-haiti.json"])
    n_articles = sum(1 for p in files if p.startswith("haiti/articles/"))
    if len(idx) != n_articles:
        failures.append(f"gate5: search index has {len(idx)} rows but {n_articles} article pages")
    for row in idx:
        if f"haiti/articles/{row['i']}.html" not in files:
            failures.append(f"gate5: search-index id '{row['i']}' has no article page")
    return failures

# --------------------------------------------------------------------- main
def main():
    if os.path.exists(HOUT):
        shutil.rmtree(HOUT)
    for d in ["articles", "decade", "paper", "topic", "assets"]:
        os.makedirs(os.path.join(HOUT, d))
    files = {}
    for i, r in enumerate(records):
        prev_r = records[i - 1] if i > 0 else None
        next_r = records[i + 1] if i < len(records) - 1 else None
        files[f'haiti/articles/{r["id"]}.html'] = article_page(r, prev_r, next_r)
    files["haiti/index.html"] = index_page()
    files["haiti/decades.html"] = decades_page()
    files["haiti/papers.html"] = papers_page()
    files["haiti/topics.html"] = topics_page()
    for d in decades_all:
        crumb = f'<a href="../decades.html">{L("nav_decades")}</a>'
        for rel, html in listing_pages("decade", decade_slug[d], f"{d}s", decade_pair(d),
                                       decade_records[d], crumb).items():
            files[rel] = html
    for p in papers:
        for rel, html in listing_pages("paper", paper_slug[p], p, esc(p), paper_records[p],
                                       f'<a href="../papers.html">{L("nav_papers")}</a>').items():
            files[rel] = html
    for t in topics_all:
        for rel, html in listing_pages("topic", topic_slug[t], TOPIC_LABELS[t][1], topic_label_pair(t),
                                       topic_records[t],
                                       f'<a href="../topics.html">{L("nav_topics")}</a>').items():
            files[rel] = html
    files["haiti/assets/search-index-haiti.json"] = search_index()
    for rel, content in files.items():
        with open(os.path.join(OUT, rel), "w", encoding="utf-8") as f:
            f.write(content)
    n_passage = sum(1 for r in records if r["passage"].strip())
    print(f"haiti built: {len(records)} records, {len(papers)} papers, "
          f"{len(decades_all)} decades, {len(topics_all)} topics, "
          f"{n_passage} with passage, {len(cluster_siblings)} pages with reprint plates, "
          f"{len(files)} files total")
    failures = run_gates(files)
    if failures:
        print(f"\nGATES FAILED ({len(failures)}):")
        for f_ in failures[:60]:
            print("  -", f_)
        sys.exit(1)
    print("gates: all 5 pass (attributes clean, no raw keys in visible text, "
          "STR + labels complete, no dead internal links, search index matches pages)")

if __name__ == "__main__":
    main()
