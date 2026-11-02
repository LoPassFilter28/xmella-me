#!/usr/bin/env python3
"""Build the xmella.me US/DR Newspaper Timeline site - v5.

PiK0's v5 order (2026-11-01 night, after the v4 review): raise the site to
the 407 FYI standard and fix the three bilingual defects at the root:

1. Bilingualism is structural, not remembered. EVERY chrome string lives
   in one string table (STR, key -> {"en", "es"}). Element text renders
   as span pairs; language-dependent ATTRIBUTES (placeholder, aria-label,
   option text) are plain text carried in data-en/data-es and swapped by
   the toggle script. Helper output never goes into an attribute.
2. Internal taxonomy keys never render. Topics pass through a merge map
   into one reader vocabulary; every key carries a bilingual label, and
   an unmapped key FAILS the build.
3. The build ends with gates (markup in attributes, raw keys in visible
   text, missing translations, stale coverage literals, dead internal
   links, search-index/page mismatch) and exits nonzero on any failure.

Design stays v4: Walnut/Terracotta tokens, Book Cover masthead, beveled
plates, plate images, flag buttons, theme toggle, Spanish default, no
technical apparatus on public pages.

Merge (all sources audited; counts printed and written to the report):
  - originals: bundle site/data/timeline.json (1,418 records)
  - grey: verdict "include" rows of data/grey-verdicts.jsonl joined with
    data/grey-summaries*.jsonl (summary/summary_es/topics) and
    data/grey-review-staging.jsonl (newspaper/date/place/url/excerpt).
    Null-summary (needs_review) rows and rows with no summary are NOT
    ingested; they are listed for the report.
  - newspapers.com: the 12 candidates in
    handoff/full/deep-dig/np_timeline_candidates.json, passage-only.
  - post-1963: the deep-dig's 7 out-of-range records; the 5 already in
    the NP-12 ingest as NP, the remaining 2 (np022-2, np022-3) ingest
    from the corpus, passage-only. Any of these dated after 1963 gets
    the era "Later years".
  - misc: verdict "misc" rows (84) become the Miscellaneous section.
Output: ~/workspace/chronicling-america/pilot-site/ (static)
"""
import json, glob, hashlib, os, re, shutil, sys
from html import escape as esc
from datetime import date as _date

BASE = os.path.expanduser("~/workspace/chronicling-america")
BDATA = os.path.join(BASE, "handoff/bundle/site/data")
CORPUS = os.path.join(BASE, "handoff/full/bundle/pipeline/s3_records/output/records.jsonl")
NPFILE = os.path.join(BASE, "handoff/full/deep-dig/np_timeline_candidates.json")
OUT = os.path.join(BASE, "pilot-site")
PAGE_SIZE = 100
SITE_BASE = "https://xmella.me/us-dr-newspaper-timeline/"

QA_HOLD = {"cr19774-2"}
QA_FLAG = {"cr10985-1", "cr00232-2"}
QUARANTINE_KNOWN = {"cr38078-1", "cr22764-1", "cr31849-1", "cr06650-1", "cr23239-2"}
LATER_ERA = "Later years"

# ---------------------------------------------------------------- data load
def load_json(p):
    d = json.load(open(p, encoding="utf-8"))
    return d if isinstance(d, list) else d.get("records", [])

def load_jsonl(p):
    rows = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows

originals = load_json(os.path.join(BDATA, "timeline.json"))
eras_data = load_json(os.path.join(BDATA, "eras.json"))

corpus = {}
with open(CORPUS, encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        corpus[r["record_id"]] = {"excerpt": r.get("excerpt") or "",
                                  "sha": r.get("excerpt_sha256") or "",
                                  "lccn": r.get("lccn") or "",
                                  "place": r.get("place") or "",
                                  "newspaper": r.get("newspaper") or "",
                                  "date": r.get("publication_date") or "",
                                  "topics": r.get("topics") or []}

# latest extraction row per id (v4 logic, unchanged)
ext = {}
for f in [os.path.join(BASE, "data/extraction.jsonl")] + sorted(glob.glob(os.path.join(BASE, "data/extraction-lane*.jsonl"))):
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

# ------------------------------------------------------- topic vocabulary
# The collection grew two taxonomies: the bundle's keys and the grey
# pass vocabulary. They merge into ONE reader vocabulary here. Any key
# not in TOPIC_LABELS after merging fails the build (gate in main()).
TOPIC_MERGE = {
    # bundle vocabulary -> reader vocabulary
    "diplomacy_treaties": "diplomacy_treaties",
    "revolution_unrest": "revolution_unrest",
    "haitian_occupation": "haiti_relations",
    "finance_markets_bonds": "finance_debt",
    "sugar_trade_economy": "trade_sugar",
    "culture_sports_tourism": "culture_society",
    "independence_1844": "independence_1844",
    "shipping_vessels_naval": "naval_military",
    "disaster_hurricane_quake": "natural_disaster",
    "samana_american_migration": "samana_bay",
    "annexation_restoration_1861": "annexation_debate",
    "mella_family": "mella_family",
    "grant_annexation_samana_bay": "annexation_debate",
    "customs_receivership_loans": "customs_receivership",
    "us_occupation_marines": "occupation_1916",
    "trujillo_regime": "trujillo_era",
    "haiti_border_massacre_1937": "haiti_relations",
    "trujillo_assassination_1961": "trujillo_era",
    "civil_war_intervention_1965": "us_intervention",
    # grey vocabulary passes through
    "annexation_debate": "annexation_debate",
    "samana_bay": "samana_bay",
    "trade_sugar": "trade_sugar",
    "trade_general": "trade_general",
    "us_intervention": "us_intervention",
    "occupation_1916": "occupation_1916",
    "trujillo_era": "trujillo_era",
    "haiti_relations": "haiti_relations",
    "immigration": "immigration",
    "naval_military": "naval_military",
    "elections_politics": "elections_politics",
    "natural_disaster": "natural_disaster",
    "culture_society": "culture_society",
    "emigration": "emigration",
    "finance_debt": "finance_debt",
    "press_media": "press_media",
    "unclassified": "unclassified",
}
TOPIC_LABELS = {
    "diplomacy_treaties": ("Diplomacy & Treaties", "Diplomacia y tratados"),
    "revolution_unrest": ("Revolution & Unrest", "Revolución y disturbios"),
    "annexation_debate": ("The Annexation Debate", "El debate de la anexión"),
    "samana_bay": ("Samaná Bay", "Bahía de Samaná"),
    "trade_sugar": ("Sugar & Trade", "Azúcar y comercio"),
    "trade_general": ("Trade", "Comercio"),
    "us_intervention": ("U.S. Intervention", "Intervención estadounidense"),
    "occupation_1916": ("The 1916–1924 Occupation", "La ocupación de 1916–1924"),
    "trujillo_era": ("The Trujillo Era", "La era de Trujillo"),
    "haiti_relations": ("Haiti & the Island", "Haití y la isla"),
    "immigration": ("Immigration", "Inmigración"),
    "naval_military": ("Naval & Military", "Asuntos navales y militares"),
    "elections_politics": ("Elections & Politics", "Elecciones y política"),
    "natural_disaster": ("Storms & Disasters", "Tormentas y desastres"),
    "culture_society": ("Life & Culture", "Vida y cultura"),
    "emigration": ("Emigration", "Emigración"),
    "finance_debt": ("Debt & Finance", "Deuda y finanzas"),
    "press_media": ("The Press", "La prensa"),
    "unclassified": ("Other", "Otros"),
    # extensions the data requires
    "independence_1844": ("Independence, 1844", "La independencia de 1844"),
    "customs_receivership": ("The Customs Receivership", "La receptoría de aduanas"),
    "mella_family": ("The Mella Family", "La familia Mella"),
}

def norm_topics(keys):
    out = []
    for k in keys or []:
        nk = TOPIC_MERGE.get(k, k)
        if nk not in out:
            out.append(nk)
    return out

# ------------------------------------------------------------------- eras
ERA_INFO = {}   # era_key -> {"en","es","years","summary_en","summary_es","start"}
for e in eras_data:
    yrs = (e.get("years") or "").replace("–", "-").split("-")
    try:
        start = int(yrs[0].strip())
        end = int(yrs[1].strip())
    except Exception:
        start, end = 0, 9999
    ERA_INFO[e["era_key"]] = {"en": e.get("title_en") or e["era_key"],
                              "es": e.get("title_es") or e["era_key"],
                              "years": e.get("years") or "",
                              "summary_en": e.get("summary_en") or "",
                              "summary_es": e.get("summary_es") or "",
                              "start": start, "end": end}

def era_for_date(iso):
    try:
        y = int((iso or "")[:4])
    except Exception:
        return None
    for key, info in ERA_INFO.items():
        if info["start"] <= y <= info["end"]:
            return key
    # nearest era by distance to its range
    return min(ERA_INFO, key=lambda k: min(abs(y - ERA_INFO[k]["start"]), abs(y - ERA_INFO[k]["end"])))

# ------------------------------------------------------------------ merge
def base_record(rid, date, newspaper, place, source_url, summary, summary_es,
                topics, era, source_tag, passage):
    return {"id": rid, "date": date or "", "newspaper": newspaper or "",
            "place": place or "", "source_url": source_url or "",
            "summary": summary or "", "summary_es": summary_es or "",
            "topics": norm_topics(topics), "era": era or "",
            "source_tag": source_tag, "passage": passage or ""}

records = []
for r in originals:
    records.append(base_record(
        r["id"], r["date"], r["newspaper"], r["place"], r["source_url"],
        r.get("summary"), r.get("summary_es"), r.get("topics"), r["era"],
        "original", corpus.get(r["id"], {}).get("excerpt", "")))
orig_ids = {r["id"] for r in records}

# grey pass
verdicts = {r["record_id"]: r for r in load_jsonl(os.path.join(BASE, "data/grey-verdicts.jsonl"))}
staging = {r["record_id"]: r for r in load_jsonl(os.path.join(BASE, "data/grey-review-staging.jsonl"))}
summaries = {}
_sum_files = sorted(glob.glob(os.path.join(BASE, "data/grey-summaries-part*.jsonl")))
_merged = os.path.join(BASE, "data/grey-summaries.jsonl")
if os.path.exists(_merged):
    _sum_files.append(_merged)  # the consolidated file is authoritative, read last
for f in _sum_files:
    for r in load_jsonl(f):
        summaries[r["record_id"]] = r
grey_excluded = []   # (record_id, why) for the report
grey_n = 0
for rid, v in verdicts.items():
    if v.get("verdict") != "include":
        continue
    s = summaries.get(rid)
    if s is None:
        grey_excluded.append((rid, "no summary row was written (summaries file incomplete)"))
        continue
    if s.get("summary") is None:
        grey_excluded.append((rid, "needs_review: " + (s.get("needs_review") or "summary withheld")))
        continue
    st = staging.get(rid, {})
    if rid in orig_ids:
        grey_excluded.append((rid, "already in the timeline"))
        continue
    records.append(base_record(
        rid, st.get("publication_date"), st.get("newspaper"), st.get("place"),
        st.get("source_url"), s.get("summary"), s.get("summary_es"),
        s.get("topics"), era_for_date(st.get("publication_date")),
        "grey", corpus.get(rid, {}).get("excerpt") or st.get("excerpt")))
    grey_n += 1

# newspapers.com 12 + the 2 remaining post-1963 records
np_rows = load_json(NPFILE)
np_ids = []
for r in np_rows:
    rid = r["record_id"]
    if rid in orig_ids or any(x["id"] == rid for x in records):
        continue
    era = LATER_ERA if (r.get("publication_date") or "") > "1963-12-31" else era_for_date(r.get("publication_date"))
    records.append(base_record(
        rid, r.get("publication_date"), r.get("newspaper"), r.get("place"),
        r.get("source_url"), "", "", r.get("topics"), era,
        "np", r.get("excerpt") or corpus.get(rid, {}).get("excerpt", "")))
    np_ids.append(rid)
post63_extra = []
for rid in ("np022-2", "np022-3"):
    c = corpus.get(rid)
    if not c or any(x["id"] == rid for x in records):
        continue
    records.append(base_record(
        rid, c.get("date"), c.get("newspaper"), c.get("place"), "",
        "", "", c.get("topics"), LATER_ERA, "post1963", c.get("excerpt", "")))
    post63_extra.append(rid)

records.sort(key=lambda r: (r["date"], r["id"]))
by_id = {r["id"]: r for r in records}

# miscellaneous section (verdict "misc"), kind from the verdict's own words
def misc_kind(v):
    t = ((v.get("reason") or "") + " " + (v.get("evidence") or "")).lower()
    doc_terms = ("convention", "treaty", "articles of organization", "official text",
                 "congress statement", "circular", "commission of inquiry",
                 "citizens' address", "notice to mariners", "government document")
    if any(w in t for w in doc_terms):
        return "documents"
    mail_terms = ("foreign-mail", "foreign mails", "foreign mail", "mails listing",
                  "mail ship", "mail-closing", "mail closing")
    if any(w in t for w in mail_terms):
        return "mail"
    return "listings"

misc_items = []
for rid, v in verdicts.items():
    if v.get("verdict") != "misc":
        continue
    st = staging.get(rid, {})
    misc_items.append({"id": rid, "date": st.get("publication_date") or "",
                       "newspaper": st.get("newspaper") or "", "place": st.get("place") or "",
                       "source_url": st.get("source_url") or "",
                       "passage": st.get("excerpt") or corpus.get(rid, {}).get("excerpt", ""),
                       "kind": misc_kind(v)})
misc_items.sort(key=lambda r: (r["date"], r["id"]))

# reprint trails
trails = {}
_tp = os.path.join(BASE, "data/reprint-trails.json")
if os.path.exists(_tp):
    trails = json.load(open(_tp, encoding="utf-8"))

# ------------------------------------------------------------ derived sets
def is_full(r):
    e = ext.get(r["id"], {})
    return bool(e.get("status") == "ok" and e.get("article_text"))

def display_name(r):
    e = ext.get(r["id"], {})
    if is_full(r) and e.get("headline_as_printed"):
        return e["headline_as_printed"]
    return r["newspaper"]

n_full = sum(1 for r in records if is_full(r))
papers = sorted({r["newspaper"] for r in records})
years = (records[0]["date"][:4], records[-1]["date"][:4])
topics_all = sorted({t for r in records for t in r["topics"]})
places_all = sorted({r["place"] for r in records if r["place"]})
era_names = sorted({r["era"] for r in records},
                   key=lambda e: (ERA_INFO.get(e, {}).get("start", 9999), e))

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
era_records = {e: [r for r in records if r["era"] == e] for e in era_names}
paper_records = {p: [r for r in records if r["newspaper"] == p] for p in papers}
topic_records = {t: [r for r in records if t in r["topics"]] for t in topics_all}
place_records = {p: [r for r in records if r["place"] == p] for p in places_all}

def npages(rs):
    return max(1, (len(rs) + PAGE_SIZE - 1) // PAGE_SIZE)

# window-bleed screen (workshop only, originals as in v4)
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
for r in records:
    if r["source_tag"] == "original" and bleed_suspect(r["passage"]):
        FLAG_BLEED.add(r["id"])

# workshop digest gate over the originals only (never printed on pages)
gate_ok = 0
for r in originals:
    c = corpus.get(r["id"], {})
    if c.get("excerpt") and hashlib.sha256(c["excerpt"].encode("utf-8")).hexdigest() == r.get("excerpt_sha256") == c.get("sha"):
        gate_ok += 1
print(f"merge: {len(originals)} originals + {grey_n} grey + {len(np_ids)} newspapers.com "
      f"+ {len(post63_extra)} post-1963 = {len(records)} records; {len(misc_items)} misc items")
print(f"grey excluded from ingest: {len(grey_excluded)}")
print(f"digest gate (workshop): {gate_ok}/{len(originals)}")
if gate_ok != len(originals):
    print("BUILD FAILED: excerpt digest gate")
    sys.exit(1)

# ------------------------------------------------------------- STR table
# EVERY user-facing chrome string, both languages, one place. Element
# text renders through L()/LT(); attributes through A()/AT(). A key with
# an empty side fails gate 3.
STR = {
    "site_sub": ("The Dominican Republic in the American Press: United States newspaper coverage of the island, gathered and translated for readers in both languages",
                 "La República Dominicana en la prensa estadounidense: la cobertura de la isla en los periódicos de Estados Unidos, reunida y traducida para lectores en ambos idiomas"),
    "kicker_loc": ("Library of Congress", "Biblioteca del Congreso"),
    "meta_desc_index": ("A bilingual collection of United States newspaper coverage of the Dominican Republic, {y0} to {y1}: {n} articles from {p} newspapers, in the order they appeared.",
                        "Una colección bilingüe de la cobertura de la República Dominicana en los periódicos de Estados Unidos, de {y0} a {y1}: {n} artículos de {p} periódicos, en el orden en que aparecieron."),
    "nav_timeline": ("Timeline", "Cronología"),
    "nav_eras": ("Eras", "Épocas"),
    "nav_papers": ("Newspapers", "Periódicos"),
    "nav_topics": ("Topics", "Temas"),
    "nav_places": ("Places", "Lugares"),
    "nav_misc": ("Miscellaneous", "Miscelánea"),
    "nav_method": ("About & Sources", "Acerca de y fuentes"),
    "theme_dark": ("Dark", "Oscuro"),
    "theme_light": ("Light", "Claro"),
    "footer_line": ("Every article links back to its original page at the Library of Congress. Observations and corrections are welcome:",
                    "Cada artículo enlaza a su página original en la Biblioteca del Congreso. Observaciones y correcciones son bienvenidas:"),
    "stat_articles": ("Articles", "Artículos"),
    "stat_papers": ("Newspapers", "Periódicos"),
    "stat_years": ("Years covered", "Años"),
    "stat_full": ("Full texts ready", "Textos completos"),
    "stat_eras": ("Eras", "Épocas"),
    "intro": ("For over a century, American newspapers kept a close eye on the Dominican Republic: its ports and presidents, its sugar and its storms, its revolutions and its baseball. This site gathers that coverage in one place, in the order it appeared, in English and Spanish. Some articles are here in full; the rest carry a summary and the passage it came from, with the original page always one click away. The collection is still growing, and readers who know something we don't are invited to send an observation from any article page.",
              "Durante más de un siglo, los periódicos estadounidenses siguieron de cerca a la República Dominicana: sus puertos y presidentes, su azúcar y sus tormentas, sus revoluciones y su béisbol. Este sitio reúne esa cobertura en un solo lugar, en el orden en que apareció, en inglés y en español. Algunos artículos están aquí completos; los demás llevan un resumen y el pasaje del que salió, con la página original siempre a un clic. La colección sigue creciendo, y quien sepa algo que nosotros no sabemos puede enviar una observación desde cualquier página de artículo."),
    "search_ph": ("Search headlines, papers, places, summaries", "Buscar titulares, periódicos, lugares, resúmenes"),
    "search_aria": ("Search the timeline", "Buscar en la cronología"),
    "filter_era_aria": ("Filter by era", "Filtrar por época"),
    "filter_topic_aria": ("Filter by topic", "Filtrar por tema"),
    "all_eras": ("All eras", "Todas las épocas"),
    "all_topics": ("All topics", "Todos los temas"),
    "search_hint": ("Search the full timeline (accents optional), filter by era or topic, or browse below. Results appear 50 at a time.",
                    "Busque en toda la cronología (acentos opcionales), filtre por época o tema, o explore más abajo. Los resultados aparecen de 50 en 50."),
    "results_count": ("{n} of {total} articles", "{n} de {total} artículos"),
    "results_none": ("Nothing matches that search yet. Try fewer words, or browse by era, newspaper, topic, or place.",
                     "Nada coincide con esa búsqueda todavía. Pruebe con menos palabras, o explore por época, periódico, tema o lugar."),
    "show_more": ("Show more results", "Mostrar más resultados"),
    "chips_h": ("Browse by topic", "Explorar por tema"),
    "paths_h": ("Reading paths", "Caminos de lectura"),
    "path1_t": ("The Annexation Story", "La historia de la anexión"),
    "path1_d": ("Twice in one century the papers argued over annexing the country: to Spain in 1861, and to the United States in the years after. These are the articles that carried the fight.",
                "Dos veces en un siglo los periódicos discutieron la anexión del país: a España en 1861 y a Estados Unidos en los años siguientes. Estos son los artículos que llevaron la pelea."),
    "path2_t": ("Samaná and the Americans", "Samaná y los estadounidenses"),
    "path2_d": ("The bay everyone wanted: whalers and coal stations, a colony of freed American families, and a century of schemes drawn on one perfect harbor.",
                "La bahía que todos querían: balleneros y estaciones de carbón, una colonia de familias estadounidenses liberadas y un siglo de planes trazados sobre un puerto perfecto."),
    "path3_t": ("The Trujillo Years in the American Press", "Los años de Trujillo en la prensa estadounidense"),
    "path3_d": ("Thirty-one years of dictatorship as American readers watched it happen, from the first profiles to the assassination and what came after.",
                "Treinta y un años de dictadura tal como los lectores estadounidenses los vieron pasar, desde los primeros perfiles hasta el magnicidio y lo que vino después."),
    "path4_t": ("Storms at Sea and Ashore", "Tormentas en el mar y en tierra"),
    "path4_d": ("Hurricanes that remade cities, earthquakes, and the ships that did not come home: the disasters the papers could not stop reporting.",
                "Huracanes que rehícieron ciudades, terremotos y los barcos que no volvieron: los desastres que los periódicos no podían dejar de contar."),
    "browse_era_h": ("Browse by era", "Explorar por época"),
    "browse_catalog_h": ("Browse the catalog", "Explorar el catálogo"),
    "period_label": ("Historical period", "Período histórico"),
    "articles_word": ("articles", "artículos"),
    "pages_word": ("pages", "páginas"),
    "background_note": ("Background chapter: no articles in this collection yet", "Capítulo de contexto: aún sin artículos en esta colección"),
    "browse_era_link": ("Browse this era", "Ver esta época"),
    "full_text": ("Full text", "Texto completo"),
    "passage_label": ("Passage", "Pasaje"),
    "summary_label": ("Summary", "Resumen"),
    "hold_h": ("Summary on hold", "Resumen en espera"),
    "hold_p": ("The summary we first wrote for this article did not match it closely enough, so we are not showing it. The passage found on the page is below, and the original page is one click away, until the article itself is ready.",
               "El primer resumen que escribimos para este artículo no coincidía lo bastante con su contenido, así que no lo mostramos. Abajo está el pasaje encontrado en la página, y la página original está a un clic, hasta que el artículo mismo esté listo."),
    "bleed_note": ("A note: the passage found for this article seems to run into the item beside it on the page, so read this summary as a first pass until the article itself is ready.",
                   "Una nota: el pasaje encontrado para este artículo parece mezclarse con el texto vecino en la página, así que lea este resumen como una primera versión hasta que el artículo mismo esté listo."),
    "source_label": ("Source", "Fuente"),
    "see_original": ("See the original page", "Ver la página original"),
    "passage_h": ("From the original page", "De la página original"),
    "passage_intro_summary": ("The passage where this article was found, copied from the newspaper page itself, reading errors and all. This is exactly what the summary above is based on.",
                              "El pasaje donde se encontró este artículo, copiado de la propia página del periódico, con sus errores de lectura y todo. Esto es exactamente aquello en lo que se basa el resumen de arriba."),
    "passage_intro_full": ("The passage where this article was found on the page, copied from the newspaper itself, reading errors and all.",
                           "El pasaje donde se encontró este artículo en la página, copiado del propio periódico, con sus errores de lectura y todo."),
    "passage_intro_only": ("This page carries the passage as it was found on the newspaper page, copied with its reading errors and all. The article's fuller presentation is still to come; the original page is linked above.",
                           "Esta página lleva el pasaje tal como se encontró en la página del periódico, copiado con sus errores de lectura y todo. La presentación completa del artículo aún está por venir; la página original está enlazada arriba."),
    "status_h": ("Where this stands", "En qué punto está"),
    "status_p": ("The full text of this article is still being prepared. Until it is ready, this page carries a summary, the passage found on the page, and the link to the original, which is always one click away.",
                 "El texto completo de este artículo aún se está preparando. Hasta que esté listo, esta página lleva un resumen, el pasaje encontrado en la página y el enlace al original, que siempre está a un clic."),
    "qa_hold_h": ("Still being checked", "Aún en revisión"),
    "qa_hold_p": ("We are still comparing this article's text against the original page, so the full text is not shown yet. The summary, the passage from the page, and the page itself are here in the meantime.",
                  "Todavía estamos comparando el texto de este artículo con la página original, así que el texto completo aún no se muestra. Mientras tanto están aquí el resumen, el pasaje de la página y la página misma."),
    "dateline_h": ("Dateline as printed", "Lugar y fecha según el original"),
    "qa_flag_h": ("A note on this text", "Una nota sobre este texto"),
    "qa_flag_p": ("We are still confirming this text line by line against the original page. If a sentence reads oddly, check it against the page linked above.",
                  "Todavía estamos confirmando este texto línea por línea contra la página original. Si alguna frase se lee rara, contrástela con la página enlazada arriba."),
    "cite_h": ("How to cite this article", "Cómo citar este artículo"),
    "references_h": ("References", "Referencias"),
    "observe_h": ("Send an observation", "Enviar una observación"),
    "observe_p": ("Does this article connect with your family, your town, or something you know? Did we get something wrong? Write to us. Observations go to the editor's inbox and are read by a person.",
                  "¿Este artículo conecta con su familia, su pueblo o algo que usted conoce? ¿Nos equivocamos en algo? Escríbanos. Las observaciones llegan al buzón del editor y las lee una persona."),
    "observe_btn": ("Send observation", "Enviar observación"),
    "context_h": ("In context", "En contexto"),
    "more_on": ("More on {label}", "Más sobre {label}"),
    "earlier_article": ("Earlier article", "Artículo anterior"),
    "later_article": ("Later article", "Artículo siguiente"),
    "also_ran_h": ("This story also ran in", "Esta historia también apareció en"),
    "np_credit": ("Obtained from newspapers.com", "Obtenido de newspapers.com"),
    "page_word": ("Page", "Página"),
    "of_word": ("of", "de"),
    "pager_earlier": ("Earlier", "Anteriores"),
    "pager_later": ("Later", "Siguientes"),
    "eras_h1": ("Era chapters", "Capítulos de época"),
    "eras_about_h": ("About these essays", "Sobre estos ensayos"),
    "eras_about_p": ("The era essays are background, written to set the scene for the articles of their years. The articles are the evidence; the essays are the frame. Era ranges are historical periods, and the collection itself runs {y0} to {y1}.",
                     "Los ensayos de época son contexto, escritos para ambientar los artículos de sus años. Los artículos son la evidencia; los ensayos, el marco. Los rangos de época son períodos históricos, y la colección misma va de {y0} a {y1}."),
    "papers_h1": ("Newspaper directory", "Directorio de periódicos"),
    "papers_intro": ("Every newspaper title in the collection, with its Library of Congress Control Number (LCCN), publication places, and article count.",
                     "Cada periódico de la colección, con su número de control de la Biblioteca del Congreso (LCCN), lugares de publicación y número de artículos."),
    "lccn_label": ("Library catalog no.", "Núm. de catálogo"),
    "topics_h1": ("Topics", "Temas"),
    "topics_intro": ("Every subject this collection is organized by. Pick one and follow it through the whole timeline.",
                     "Cada tema que organiza esta colección. Elija uno y sígalo a través de toda la cronología."),
    "places_h1": ("Places of publication", "Lugares de publicación"),
    "misc_h1": ("Miscellaneous", "Miscelánea"),
    "misc_intro": ("Not every valuable thing in a newspaper is an article. The papers also printed treaties and official statements in full, directories of sailings to Dominican ports, and the mail tables that show how letters moved between the United States and the island. This section gathers those pages and presents each one as it was printed, with its newspaper and date.",
                   "No todo lo valioso en un periódico es un artículo. Los periódicos también imprimieron tratados y declaraciones oficiales completos, directorios de travesías a puertos dominicanos y las tablas de correo que muestran cómo viajaban las cartas entre Estados Unidos y la isla. Esta sección reúne esas páginas y presenta cada una tal como se imprimió, con su periódico y su fecha."),
    "kind_documents": ("Documents", "Documentos"),
    "kind_listings": ("Listings & directories", "Listados y directorios"),
    "kind_mail": ("Mail & sailings", "Correo y travesías"),
    "misc_passage_h": ("From the page", "De la página"),
    "method_h1": ("About this collection, and its sources", "Acerca de esta colección y sus fuentes"),
    "method_p1": ("Everything here comes from one place: the Library of Congress and its Chronicling America archive, which preserves American newspapers page by page. This collection gathers the coverage of the Dominican Republic: {n} articles from {p} newspapers, {y0} to {y1}, in the order they were published. Every article page names its newspaper and date and links to the original page at the Library, so anything you read here can be checked against the source in one click.",
                  "Todo lo que hay aquí viene de un solo lugar: la Biblioteca del Congreso y su archivo Chronicling America, que conserva los periódicos estadounidenses página por página. Esta colección reúne la cobertura de la República Dominicana: {n} artículos de {p} periódicos, de {y0} a {y1}, en el orden en que se publicaron. Cada página de artículo nombra su periódico y su fecha y enlaza a la página original en la Biblioteca, así que todo lo que lea aquí puede contrastarse con la fuente en un clic."),
    "method_p2_h": ("Full texts and summaries.", "Textos completos y resúmenes."),
    "method_p2": ("Articles are still being prepared one by one. Where the full text is ready, you will see the article itself, just the article, without the items that sat beside it on the page. Where it is not ready yet, the page carries a summary, and under it the passage the summary was written from, copied from the newspaper page with its reading errors and all. A summary is labeled as a summary. Nothing here pretends to be the article when it is not.",
                  "Los artículos se siguen preparando uno por uno. Donde el texto completo está listo, verá el artículo mismo, solo el artículo, sin los textos que tenía al lado en la página. Donde aún no está listo, la página lleva un resumen y, debajo, el pasaje del que se escribió el resumen, copiado de la página del periódico con sus errores de lectura y todo. Un resumen se etiqueta como resumen. Nada aquí finge ser el artículo cuando no lo es."),
    "method_p3_h": ("What belongs here.", "Qué pertenece aquí."),
    "method_p3": ("An article belongs in this collection when it is substantially about the Dominican Republic, under any of its historical names, including Santo Domingo: its government, its people, its land, or its dealings with the United States and the world. Articles mainly about Haiti are included when they take up Santo Domingo or the whole island in earnest; a passing mention is not enough. In nineteenth-century newspapers the word \"Dominica\" often meant this country, and those cases are judged by context; the island of Dominica is a different place and stays out.",
                  "Un artículo pertenece a esta colección cuando trata sustancialmente de la República Dominicana, con cualquiera de sus nombres históricos, incluido Santo Domingo: su gobierno, su gente, su tierra o sus relaciones con Estados Unidos y el mundo. Los artículos principalmente sobre Haití se incluyen cuando abordan en serio a Santo Domingo o a la isla entera; una mención pasajera no basta. En los periódicos del siglo XIX la palabra «Dominica» a menudo nombraba a este país, y esos casos se juzgan por contexto; la isla de Dominica es otro lugar y queda fuera."),
    "method_p4_h": ("Beyond the Library's pages.", "Más allá de las páginas de la Biblioteca."),
    "method_p4": ("A small number of articles come from newspapers.com rather than the Library of Congress; each of those pages says so, plainly, where its source is named. The Miscellaneous section gathers the documents, sailing directories, and mail tables the papers printed alongside the news. A few articles from after {y1_main} are included because the story they belong to runs past that year; they sit in their own era, Later years, rather than pretending the timeline always meant to reach them.",
                  "Un pequeño número de artículos viene de newspapers.com y no de la Biblioteca del Congreso; cada una de esas páginas lo dice, claramente, donde se nombra su fuente. La sección Miscelánea reúne los documentos, directorios de travesías y tablas de correo que los periódicos imprimieron junto a las noticias. Unos pocos artículos posteriores a {y1_main} se incluyen porque la historia a la que pertenecen sigue más allá de ese año; están en su propia época, Años posteriores, en vez de fingir que la cronología siempre quiso llegar hasta ellos."),
    "method_p5_h": ("Two kinds of knowing.", "Dos maneras de saber."),
    "method_p5": ("Where this site states something beyond the articles themselves, it says which kind of knowledge it is. Documented means a primary source backs it and is cited. Oral tradition means it comes from family or community memory: valued, printed as it was told, and possibly not exact. The label travels with the claim, so a careful reader always knows what they are standing on.",
                  "Cuando este sitio afirma algo más allá de los propios artículos, dice de qué clase de conocimiento se trata. Documentado significa que una fuente primaria lo respalda y se cita. Tradición oral significa que viene de la memoria familiar o comunitaria: se valora, se imprime tal como se contó y puede no ser exacto. La etiqueta acompaña a la afirmación, para que un lector cuidadoso sepa siempre sobre qué está parado."),
    "method_p6_h": ("Corrections and observations.", "Correcciones y observaciones."),
    "method_p6": ("This is a living collection and it will have mistakes. Every article page has a Send Observation box; observations go to admin@xmella.me and are read by a person. If your family appears in these pages, we especially want to hear from you.",
                  "Esta es una colección viva y tendrá errores. Cada página de artículo tiene un recuadro para enviar una observación; las observaciones llegan a admin@xmella.me y las lee una persona. Si su familia aparece en estas páginas, queremos saber de usted especialmente."),
    "later_summary": ("Coverage that runs past the collection's main years. The newspapers kept watching the island after 1963, and these later articles belong with the story they continue.",
                      "Cobertura que sigue más allá de los años principales de la colección. Los periódicos siguieron mirando la isla después de 1963, y estos artículos tardíos pertenecen a la historia que continúan."),
    "notfound_h": ("Page not found", "Página no encontrada"),
    "notfound_p": ("That page is not part of this collection. The timeline itself is one click away.",
                   "Esa página no forma parte de esta colección. La cronología está a un clic."),
    "notfound_home": ("Back to the timeline", "Volver a la cronología"),
    "doc_label": ("Documented", "Documentado"),
    "oral_label": ("Oral tradition", "Tradición oral"),
}

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
           "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
}

def ST(key, lang):
    return STR[key][0] if lang == "en" else STR[key][1]

def L(key, **fmt):
    """Bilingual element text: a span pair, one per language."""
    en, es = STR[key]
    if fmt:
        en, es = en.format(**fmt), es.format(**fmt)
    return f'<span class="l-en">{esc(en)}</span><span class="l-es">{esc(es)}</span>'

def Lp(en, es):
    """Span pair for data-carried text (era titles, era summaries)."""
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
    """data-en/data-es/data-attr only, for elements whose visible text is
    itself the swapped slot (<option>)."""
    en, es = STR[key]
    return f'data-en="{esc(en)}" data-es="{esc(es)}" data-attr="text"'

def fmt_date(iso):
    """A date as a bilingual span pair: 'November 29, 1820' / '29 de
    noviembre de 1820'. Falls back to the raw value if unparseable."""
    try:
        y, m, d = (int(x) for x in (iso or "")[:10].split("-"))
        _date(y, m, d)
        en = f"{MONTHS['en'][m - 1]} {d}, {y}"
        es = f"{d} de {MONTHS['es'][m - 1]} de {y}"
        return Lp(en, es)
    except Exception:
        return esc(iso or "")

def era_pair(era):
    if era == LATER_ERA:
        return Lp("Later years", "Años posteriores")
    info = ERA_INFO.get(era)
    if info:
        return Lp(info["en"], info["es"])
    return esc(era)

def era_years(era):
    if era == LATER_ERA:
        rs = era_records.get(era, [])
        if rs:
            return f'{rs[0]["date"][:4]}–{rs[-1]["date"][:4]}'
        return ""
    return ERA_INFO.get(era, {}).get("years", "")

def era_summary_pair(era):
    if era == LATER_ERA:
        return L("later_summary")
    info = ERA_INFO.get(era, {})
    return Lp(info.get("summary_en", ""), info.get("summary_es", ""))

def topic_label_pair(key):
    en, es = TOPIC_LABELS[key]
    return Lp(en, es)

# -------------------------------------------------------------------- CSS
# v4 tokens and components kept; the dark --walnut-deep value in v4 was
# an 8-digit hex (#12090302, near-transparent) and is repaired to the
# intended #120903. New rules (.chips, .doors, .ctx, a.pill, .label.kind)
# use existing tokens and existing font sizes only.
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
--walnut:#170C04;--walnut-deep:#120903;--terracotta:#D07B45;--terracotta-bright:#E08D54;
--border:#5A4030;--border-strong:#7A5B40;
--plate-hi:#3D2716;--plate-lo:#1D1106;
--shadow:0 1px 2px rgba(0,0,0,.5),0 4px 14px rgba(0,0,0,.4)}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Segoe UI","Source Sans 3",-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.6;
transition:background .25s ease,color .25s ease}
a{color:var(--terracotta)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 64px}
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
.controls select{flex:1 1 150px;min-width:0;max-width:100%}
.card{background:linear-gradient(180deg,var(--plate-hi),var(--paper-elevated) 55%);
border:1px solid var(--border-strong);border-radius:10px;padding:16px 18px;margin:0 0 14px;
box-shadow:inset 0 1px 0 rgba(255,255,255,.45),inset 0 -8px 14px -10px var(--plate-lo),var(--shadow)}
.card .meta{font-size:13px;color:var(--ink-secondary)}
.card h3{margin:4px 0 6px;font-size:18px}
.card h3 a{color:var(--ink);text-decoration:none}
.card h3 a:hover{color:var(--terracotta)}
.pills{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.pill{font-size:11px;font-weight:600;letter-spacing:.03em;border:1px solid var(--border-strong);border-radius:999px;padding:2px 9px;color:var(--ink-secondary);text-decoration:none}
a.pill:hover{color:var(--terracotta);border-color:var(--terracotta)}
.pill.full{border-color:var(--terracotta);color:var(--terracotta)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 4px}
.chip{font:inherit;font-size:12px;font-weight:600;padding:6px 12px;min-height:36px;border:1px solid var(--border-strong);
border-radius:999px;background:var(--paper-elevated);color:var(--ink-secondary);cursor:pointer}
.chip[aria-pressed="true"]{background:var(--terracotta);color:#FFF7EA;border-color:var(--terracotta)}
.doors{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
.doors .card{margin:0}
article.page{background:var(--paper-elevated);border:1px solid var(--border);border-radius:12px;
padding:26px 30px;margin-top:22px;box-shadow:var(--shadow)}
article.page h1{font-size:26px;margin:6px 0}
article.page .src{font-size:14px;color:var(--ink-secondary);border-bottom:1px solid var(--border);padding-bottom:12px}
article.page .body p{margin:0 0 14px;font-size:16px}
.well{background:var(--paper-muted);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:16px 0}
.well h4{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-secondary)}
.well p,.well a{overflow-wrap:anywhere}
.ctx{background:linear-gradient(180deg,var(--plate-hi),var(--paper-elevated) 60%);
border:1px solid var(--border-strong);border-radius:10px;padding:14px 16px;margin:16px 0;
box-shadow:inset 0 1px 0 rgba(255,255,255,.45),var(--shadow)}
.ctx h4{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-secondary)}
.ctx .pn{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:14px;margin-top:10px}
.ctx ul{margin:6px 0 0;padding-left:18px;font-size:14px}
.ctx .era-line{font-size:14px}
.label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.05em;padding:2px 8px;border-radius:3px;text-transform:uppercase}
.label.doc{background:var(--sage);color:#fff}
.label.oral{background:var(--terracotta);color:#fff}
.label.kind{background:var(--walnut);color:#FFF7EA}
.sumlabel{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--terracotta);margin:0 0 4px}
figure.plate{margin:18px 0;text-align:center;background:var(--paper-elevated);
border:1px solid var(--border-strong);border-radius:10px;padding:14px;box-shadow:var(--shadow)}
figure.plate img{max-width:100%;border:1px solid var(--border-strong)}
figure.plate figcaption{font-size:13px;color:var(--ink-secondary);margin-top:8px}
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
@media (max-width:640px){.dirlist{columns:1}.doors{grid-template-columns:1fr}article.page{padding:18px 16px}header.masthead{margin:10px 10px 0}footer{margin:30px 10px 12px}}
body[data-lang="en"] .l-es{display:none}
body[data-lang="es"] .l-en{display:none}
.hidden{display:none}
"""

FLAG_ES = ('<svg viewBox="0 0 22 15" aria-hidden="true"><rect width="22" height="15" fill="#F1BF00"/>'
           '<rect width="22" height="3.75" fill="#AA151B"/><rect y="11.25" width="22" height="3.75" fill="#AA151B"/></svg>')
FLAG_GB = ('<svg viewBox="0 0 22 15" aria-hidden="true"><rect width="22" height="15" fill="#012169"/>'
           '<path d="M0 0L22 15M22 0L0 15" stroke="#fff" stroke-width="3"/>'
           '<path d="M0 0L22 15M22 0L0 15" stroke="#C8102E" stroke-width="1.2"/>'
           '<path d="M11 0V15M0 7.5H22" stroke="#fff" stroke-width="5"/>'
           '<path d="M11 0V15M0 7.5H22" stroke="#C8102E" stroke-width="2.8"/></svg>')

# ------------------------------------------------------------- page chrome
def head(title_txt, depth=0, site_h1=False, desc_es="", extra_meta=""):
    css = ("../" * depth) + "assets/style.css"
    title_html = "<h1>US/DR Newspaper Timeline</h1>" if site_h1 else '<p class="sitename">US/DR Newspaper Timeline</p>'
    if not desc_es:
        desc_es = ST("meta_desc_index", "es").format(y0=years[0], y1=years[1], n=len(records), p=len(papers))
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(desc_es)}">
<title>{esc(title_txt)} | US/DR Newspaper Timeline</title>{extra_meta}
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

def nav(depth=0):
    p = "../" * depth
    return (f'<nav class="main"><a href="{p}index.html">{L("nav_timeline")}</a>\n'
            f'<a href="{p}eras.html">{L("nav_eras")}</a>\n'
            f'<a href="{p}papers.html">{L("nav_papers")}</a>\n'
            f'<a href="{p}topics.html">{L("nav_topics")}</a>\n'
            f'<a href="{p}places.html">{L("nav_places")}</a>\n'
            f'<a href="{p}misc.html">{L("nav_misc")}</a>\n'
            f'<a href="{p}method.html">{L("nav_method")}</a></nav>')

FOOT = f"""<footer><div class="frame">US/DR Newspaper Timeline &middot; xmella.me<br>
{L("footer_line")} <a href="mailto:admin@xmella.me">admin@xmella.me</a></div></footer>
</body></html>"""

# -------------------------------------------------------------- components
def paras(text):
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)

def clean_article_text(r, e):
    """Strip a headline repeated at the start of the article text (v4 M4)."""
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
def has_summary(r):
    return bool((r.get("summary") or "").strip())

def summary_block(r):
    if r["id"] in QUARANTINE:
        return (f'<p class="sumlabel">{L("hold_h")}</p><p>{L("hold_p")}</p>')
    out = (f'<p class="sumlabel">{L("summary_label")}</p>'
           f'<p class="l-en">{esc(r.get("summary") or "")}</p><p class="l-es">{esc(r.get("summary_es") or "")}</p>')
    if r["id"] in FLAG_BLEED:
        out += f'<p class="meta">{L("bleed_note")}</p>'
    return out

def topic_pills(r, depth=0):
    p = "../" * depth
    out = []
    for t in r["topics"]:
        out.append(f'<a class="pill" href="{p}topic/{topic_slug[t]}-1.html">{topic_label_pair(t)}</a>')
    if is_full(r):
        out.append(f'<span class="pill full">{L("full_text")}</span>')
    return "".join(out)

def meta_line(r):
    bits = [fmt_date(r["date"])]
    if r["place"]:
        bits.append(esc(r["place"]))
    bits.append(era_pair(r["era"]))
    return " &middot; ".join(bits)

def card(r, depth=0):
    p = "../" * depth
    if is_full(r):
        text, _ = clean_article_text(r, ext[r["id"]])
        lead = re.sub(r"\s+", " ", text).strip()[:240]
        body = f"<p>{esc(lead)}&hellip;</p>"
    elif r["id"] in QUARANTINE or has_summary(r):
        body = summary_block(r)
    else:
        lead = re.sub(r"\s+", " ", r["passage"]).strip()[:240]
        body = f'<p class="sumlabel">{L("passage_label")}</p><p>{esc(lead)}&hellip;</p>'
    src = (f'<div class="meta"><a href="{esc(r["source_url"])}">{L("see_original")}</a></div>'
           if r["source_url"] else f'<div class="meta">{L("np_credit")}</div>')
    return (f'<div class="card"><div class="meta">{meta_line(r)}</div>'
            f'<h3><a href="{p}articles/{esc(r["id"])}.html">{esc(display_name(r))}</a></h3>'
            f'{body}<div class="pills">{topic_pills(r, depth)}</div>{src}</div>')

def excerpt_well(r, mode):
    """mode: 'summary' (a summary above rests on this passage), 'full'
    (the article above was found here), 'only' (passage-only page)."""
    if not r["passage"]:
        return ""
    intro = {"summary": "passage_intro_summary", "full": "passage_intro_full",
             "only": "passage_intro_only"}[mode]
    return (f'<div class="well"><h4>{L("passage_h")}</h4><p>{L(intro)}</p>'
            f'{paras(r["passage"])}</div>')

def observe_box(r, page_path):
    from urllib.parse import quote
    subj = quote(f'Observation: {r["newspaper"]}, {r["date"]}')
    body = quote(f'{display_name(r)} ({r["date"]})\n{SITE_BASE}{page_path}\n\n')
    return (f'<div class="observe"><div class="inner"><h4>{L("observe_h")}</h4>'
            f'<p>{L("observe_p")}</p>'
            f'<a class="btn" href="mailto:admin@xmella.me?subject={subj}&body={body}">{L("observe_btn")}</a>'
            f'</div></div>')

def context_plate(r, prev_r, next_r):
    h = [f'<div class="ctx"><h4>{L("context_h")}</h4>']
    h.append(f'<div class="era-line"><b>{era_pair(r["era"])}</b> &middot; {esc(era_years(r["era"]))}</div>')
    h.append(f'<p style="margin:6px 0 0">{era_summary_pair(r["era"])}</p>')
    pn = []
    if prev_r:
        pn.append(f'<span>&larr; {L("earlier_article")}: <a href="{esc(prev_r["id"])}.html">{esc(display_name(prev_r))}</a> &middot; {fmt_date(prev_r["date"])}</span>')
    else:
        pn.append("<span></span>")
    if next_r:
        pn.append(f'<span>{L("later_article")}: <a href="{esc(next_r["id"])}.html">{esc(display_name(next_r))}</a> &middot; {fmt_date(next_r["date"])} &rarr;</span>')
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
                h.append(f'<li><a href="{esc(x["id"])}.html">{esc(display_name(x))}</a> &middot; {fmt_date(x["date"])}</li>')
            h.append("</ul>")
    h.append("</div>")
    return "".join(h)

def trails_plate(r):
    tr = trails.get(r["id"])
    if not tr or not tr.get("also_ran_in"):
        return ""
    h = [f'<div class="well"><h4>{L("also_ran_h")}</h4>']
    for sib in tr["also_ran_in"]:
        line = esc(sib.get("newspaper") or "")
        if sib.get("place"):
            line += f' &middot; {esc(sib["place"])}'
        line += f' &middot; {fmt_date(sib.get("date") or "")}'
        if sib.get("source_url"):
            h.append(f'<p><a href="{esc(sib["source_url"])}">{line}</a></p>')
        else:
            h.append(f"<p>{line}</p>")
    h.append("</div>")
    return "".join(h)

def article_page(r, prev_r, next_r):
    global STRIPPED
    e = ext.get(r["id"], {})
    full = is_full(r)
    name = display_name(r)
    desc_es = (r.get("summary_es") or r.get("summary") or f'{r["newspaper"]}, {r["date"]}')[:200]
    dc = [f'<meta name="DC.title" content="{esc(name)}">',
          f'<meta name="DC.publisher" content="{esc(r["newspaper"])}">',
          f'<meta name="DC.date" content="{esc(r["date"])}">']
    if r["source_url"]:
        dc.append(f'<meta name="DC.source" content="{esc(r["source_url"])}">')
    dc.append(f'<meta name="DC.identifier" content="{esc(r["id"])}">')
    h = [head(name, depth=1, desc_es=desc_es, extra_meta="".join(dc)), nav(depth=1),
         '<div class="wrap"><article class="page">']
    h.append(f'<div class="meta">{meta_line(r)}</div>')
    h.append(f"<h1>{esc(name)}</h1>")
    src_bits = [esc(r["newspaper"])]
    if r["place"]:
        src_bits.append(esc(r["place"]))
    src_bits.append(fmt_date(r["date"]))
    h.append(f'<div class="src">{L("source_label")}: {" &middot; ".join(src_bits)}')
    if r["source_url"]:
        h.append(f'<br><a href="{esc(r["source_url"])}">{esc(r["source_url"])}</a>')
    if r["source_tag"] in ("np", "post1963"):
        h.append(f'<br>{L("np_credit")}')
    h.append("</div>")
    if r["topics"]:
        h.append(f'<div class="pills">{topic_pills(r, depth=1)}</div>')
    h.append(context_plate(r, prev_r, next_r))
    passage_only = not full and r["id"] not in QA_HOLD and not has_summary(r) and r["id"] not in QUARANTINE
    if r["id"] in QA_HOLD:
        h.append(f'<div class="well"><h4>{L("qa_hold_h")}</h4><p>{L("qa_hold_p")}</p></div>')
        h.append(f'<div class="body">{summary_block(r)}</div>')
        h.append(excerpt_well(r, "summary"))
    elif full:
        text, stripped = clean_article_text(r, e)
        if stripped:
            STRIPPED += 1
        h.append(f'<div class="body">{paras(text)}</div>')
        if e.get("dateline"):
            h.append(f'<div class="well"><h4>{L("dateline_h")}</h4><p>{esc(e["dateline"])}</p></div>')
        if r["id"] in QA_FLAG:
            h.append(f'<div class="well"><h4>{L("qa_flag_h")}</h4><p>{L("qa_flag_p")}</p></div>')
        h.append(excerpt_well(r, "full"))
    elif passage_only:
        h.append(excerpt_well(r, "only"))
    else:
        h.append(f'<div class="body">{summary_block(r)}</div>')
        h.append(f'<div class="well"><h4>{L("status_h")}</h4><p>{L("status_p")}</p></div>')
        h.append(excerpt_well(r, "summary"))
    h.append(trails_plate(r))
    yr = esc(r["date"][:4])
    if r["source_url"]:
        cite = (f'{esc(r["newspaper"])}. ({yr}). {esc(r["place"])}, {esc(r["date"])}. '
                f'US/DR Newspaper Timeline. Library of Congress, Chronicling America: {esc(r["source_url"])}')
        refs = (f'<p>Library of Congress, Chronicling America: '
                f'<a href="{esc(r["source_url"])}">{esc(r["newspaper"])}, {esc(r["date"])}</a>.</p>')
    else:
        cite = (f'{esc(r["newspaper"])}. ({yr}). {esc(r["date"])}. '
                f'US/DR Newspaper Timeline. {ST("np_credit", "en")} / {ST("np_credit", "es")}.')
        refs = f'<p>{L("np_credit")}: {esc(r["newspaper"])}, {esc(r["date"])}.</p>'
    h.append(f'<div class="well"><h4>{L("cite_h")}</h4><p>{cite}</p></div>')
    h.append(f'<div class="well"><h4>{L("references_h")}</h4>{refs}</div>')
    h.append(observe_box(r, f'articles/{r["id"]}.html'))
    h.append("</article></div>")
    h.append(FOOT)
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

def listing_pages(base, title_txt, title_html, rs, crumb):
    """Paginated record listings for one facet value. Returns {filename: html}."""
    out = {}
    npg = npages(rs)
    for k in range(1, npg + 1):
        chunk = rs[(k - 1) * PAGE_SIZE: k * PAGE_SIZE]
        h = [head(f"{title_txt} ({k}/{npg})", depth=1), nav(depth=1), '<div class="wrap">']
        h.append(f'<div class="meta" style="margin-top:18px">{crumb} &middot; {L("page_word")} {k} {L("of_word")} {npg}</div>')
        h.append(f"<h1>{title_html}</h1>")
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
        crumb = f'<a href="../eras.html">{L("nav_eras")}</a>'
        title_txt = "Años posteriores" if era == LATER_ERA else ERA_INFO.get(era, {}).get("es", era)
        for name, html in listing_pages(era_slug[era], title_txt, era_pair(era), era_records[era], crumb).items():
            out[f"era/{name}"] = html
    return out

def facet_pages():
    out = {}
    for p in papers:
        for name, html in listing_pages(paper_slug[p], p, esc(p), paper_records[p],
                                        f'<a href="../papers.html">{L("nav_papers")}</a>').items():
            out[f"paper/{name}"] = html
    for t in topics_all:
        for name, html in listing_pages(topic_slug[t], TOPIC_LABELS[t][1], topic_label_pair(t), topic_records[t],
                                        f'<a href="../topics.html">{L("nav_topics")}</a>').items():
            out[f"topic/{name}"] = html
    for pl in places_all:
        for name, html in listing_pages(place_slug[pl], pl, esc(pl), place_records[pl],
                                        f'<a href="../places.html">{L("nav_places")}</a>').items():
            out[f"place/{name}"] = html
    return out

# ------------------------------------------------------------- search index
def search_index():
    rows = []
    for r in records:
        if is_full(r):
            text, _ = clean_article_text(r, ext[r["id"]])
            s = re.sub(r"\s+", " ", text).strip()[:240]
            x = s
        elif r["id"] in QUARANTINE or not has_summary(r):
            s = re.sub(r"\s+", " ", r["passage"]).strip()[:240]
            x = s
        else:
            s = (r.get("summary") or "")[:240]
            x = (r.get("summary_es") or "")[:240]
        einfo = ERA_INFO.get(r["era"], {})
        rows.append({"i": r["id"], "d": r["date"], "n": r["newspaper"], "p": r["place"],
                     "e": "Later years" if r["era"] == LATER_ERA else einfo.get("en", r["era"]),
                     "z": "Años posteriores" if r["era"] == LATER_ERA else einfo.get("es", r["era"]),
                     "u": era_slug[r["era"]],
                     "t": [topic_slug[t] for t in r["topics"]],
                     "k": r["topics"],
                     "te": [TOPIC_LABELS[t][0] for t in r["topics"]],
                     "ts": [TOPIC_LABELS[t][1] for t in r["topics"]],
                     "h": display_name(r), "f": 1 if is_full(r) else 0, "s": s, "x": x})
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

SEARCH_JS = r"""
var q=document.getElementById('q'),esel=document.getElementById('fe'),tsel=document.getElementById('ft'),
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
if(m.f)pills+='<span class="pill full">'+escS(PACK[lang].full_text)+'</span>';
return '<div class="card"><div class="meta">'+escS(fmtD(m.d,lang))+' &middot; '+escS(m.p)+' &middot; '+escS(lang=='es'?m.z:m.e)+'</div>'+
'<h3><a href="articles/'+m.i+'.html">'+escS(m.h)+'</a></h3>'+
'<p>'+escS(lang=='es'?(m.x||m.s):m.s)+'</p>'+
(pills?'<div class="pills">'+pills+'</div>':'')+'</div>';}).join('');
cnt.textContent=matches.length?PACK[lang].results_count.replace('{n}',matches.length).replace('{total}',IDX.length):PACK[lang].results_none;
more.classList.toggle('hidden',shown>=matches.length);}
function run(){if(!IDX)return;var toks=fold(q.value).split(/\s+/).filter(Boolean);
var ef=esel.value,tf=tsel.value;active=!!(toks.length||ef||tf);
if(!active){matches=[];shown=0;render();return;}
matches=IDX.filter(function(m){if(ef&&m.u!==ef)return false;if(tf&&m.t.indexOf(tf)<0)return false;
if(!toks.length)return true;
var hay=fold(m.d+' '+m.n+' '+m.p+' '+m.e+' '+m.z+' '+m.h+' '+m.s+' '+m.x+' '+m.k.join(' ')+' '+m.te.join(' ')+' '+m.ts.join(' '));
return toks.every(function(t){return hay.indexOf(t)>-1;});});
shown=Math.min(STEP,matches.length);render();}
function load(){if(IDX){run();return;}
fetch('assets/search-index.json').then(function(r){return r.json();}).then(function(j){IDX=j;run();});}
function syncChips(){document.querySelectorAll('.chip').forEach(function(c){
c.setAttribute('aria-pressed',c.getAttribute('data-tslug')===tsel.value?'true':'false');});}
q.addEventListener('focus',load);q.addEventListener('input',function(){IDX?run():load();});
esel.addEventListener('change',function(){IDX?run():load();});
tsel.addEventListener('change',function(){syncChips();IDX?run():load();});
document.querySelectorAll('.chip').forEach(function(c){c.addEventListener('click',function(){
tsel.value=(tsel.value===c.getAttribute('data-tslug'))?'':c.getAttribute('data-tslug');
syncChips();IDX?run():load();});});
more.addEventListener('click',function(){shown=Math.min(shown+STEP,matches.length);render();});
window.__onLang=function(){if(IDX)render();};
(function(){var prm=new URLSearchParams(location.search),t=prm.get('t'),e=prm.get('e');
if(t)tsel.value=t;if(e)esel.value=e;if(t||e){syncChips();load();}})();
"""

def index_page():
    desc_es = ST("meta_desc_index", "es").format(y0=years[0], y1=years[1], n=len(records), p=len(papers))
    h = [head(ST("nav_timeline", "es"), site_h1=True, desc_es=desc_es), nav()]
    h.append('<div class="wrap">')
    h.append('<div class="stats">'
             f'<div class="stat"><b>{len(records)}</b><span>{L("stat_articles")}</span></div>'
             f'<div class="stat"><b>{len(papers)}</b><span>{L("stat_papers")}</span></div>'
             f'<div class="stat"><b>{years[0]}-{years[1]}</b><span>{L("stat_years")}</span></div>'
             f'<div class="stat"><b>{n_full}</b><span>{L("stat_full")}</span></div>'
             f'<div class="stat"><b>{len(era_names)}</b><span>{L("stat_eras")}</span></div></div>')
    h.append(f'<div class="card"><p>{L("intro")}</p></div>')
    # search + working era/topic filters (the Ask a Local pattern)
    era_opts = [f'<option value="" {AO("all_eras")}>{esc(ST("all_eras", "es"))}</option>']
    for era in era_names:
        en = "Later years" if era == LATER_ERA else ERA_INFO.get(era, {}).get("en", era)
        es = "Años posteriores" if era == LATER_ERA else ERA_INFO.get(era, {}).get("es", era)
        era_opts.append(f'<option value="{era_slug[era]}" data-en="{esc(en)}" data-es="{esc(es)}" data-attr="text">{esc(es)}</option>')
    topic_opts = [f'<option value="" {AO("all_topics")}>{esc(ST("all_topics", "es"))}</option>']
    for t in sorted(topics_all, key=lambda t: TOPIC_LABELS[t][0]):
        topic_opts.append(f'<option value="{topic_slug[t]}" data-en="{esc(TOPIC_LABELS[t][0])}" data-es="{esc(TOPIC_LABELS[t][1])}" data-attr="text">{esc(TOPIC_LABELS[t][1])}</option>')
    h.append(f"""<div class="controls">
<input type="search" id="q" {A("placeholder", "search_ph")} {A("aria-label", "search_aria")}>
<select id="fe" {A("aria-label", "filter_era_aria")}>{''.join(era_opts)}</select>
<select id="ft" {A("aria-label", "filter_topic_aria")}>{''.join(topic_opts)}</select>
</div>
<div class="meta">{L("search_hint")}</div>
<div class="meta" id="count" style="margin-top:6px"></div>
<div id="results" style="margin-top:12px"></div>
<button class="morebtn hidden" id="more">{L("show_more")}</button>""")
    # topic chips set the filter
    chips = []
    for t in sorted(topics_all, key=lambda t: -len(topic_records[t])):
        chips.append(f'<button class="chip" data-tslug="{topic_slug[t]}" aria-pressed="false">{topic_label_pair(t)}</button>')
    h.append(f'<h2 style="margin-top:28px">{L("chips_h")}</h2><div class="chips">{"".join(chips)}</div>')
    # reading paths: four doors onto topic pages
    paths = [("path1_t", "path1_d", "annexation_debate"), ("path2_t", "path2_d", "samana_bay"),
             ("path3_t", "path3_d", "trujillo_era"), ("path4_t", "path4_d", "natural_disaster")]
    doors = []
    for tk, dk, topic in paths:
        if topic in topic_records:
            doors.append(f'<div class="card"><h3><a href="topic/{topic_slug[topic]}-1.html">{L(tk)}</a></h3><p>{L(dk)}</p></div>')
    h.append(f'<h2 style="margin-top:28px">{L("paths_h")}</h2><div class="doors">{"".join(doors)}</div>')
    # browse by era
    h.append(f'<h2 style="margin-top:28px">{L("browse_era_h")}</h2>')
    for era in era_names:
        rs = era_records[era]
        h.append(f'<div class="card"><div class="meta">{L("period_label")}: {esc(era_years(era))} &middot; {len(rs)} {L("articles_word")} &middot; {npages(rs)} {L("pages_word")}</div>'
                 f'<h3><a href="era/{era_slug[era]}-1.html">{era_pair(era)}</a></h3>'
                 f'<p>{era_summary_pair(era)}</p></div>')
    for e in eras_data:
        key = e["era_key"]
        if key not in era_records:
            h.append(f'<div class="card"><div class="meta">{L("period_label")}: {esc(e.get("years") or "")} &middot; {L("background_note")}</div>'
                     f'<h3><a href="eras.html">{Lp(e.get("title_en") or "", e.get("title_es") or "")}</a></h3>'
                     f'<p>{Lp(e.get("summary_en") or "", e.get("summary_es") or "")}</p></div>')
    h.append(f'<h2 style="margin-top:28px">{L("browse_catalog_h")}</h2>')
    h.append(f'<div class="card"><p><a href="papers.html">{L("nav_papers")}</a> ({len(papers)}) &middot; '
             f'<a href="topics.html">{L("nav_topics")}</a> ({len(topics_all)}) &middot; '
             f'<a href="places.html">{L("nav_places")}</a> ({len(places_all)}) &middot; '
             f'<a href="misc.html">{L("nav_misc")}</a> ({len(misc_items)})</p></div>')
    pack = {"en": {"results_count": STR["results_count"][0], "results_none": STR["results_none"][0],
                   "full_text": STR["full_text"][0]},
            "es": {"results_count": STR["results_count"][1], "results_none": STR["results_none"][1],
                   "full_text": STR["full_text"][1]},
            "months": MONTHS}
    js = SEARCH_JS.replace("PACK", "window.PACK")
    h.append('</div>\n<script>window.PACK=' + json.dumps(pack, ensure_ascii=False) + ';</script>')
    h.append("<script>" + js + "</script>")
    h.append(FOOT)
    return "".join(h)

# ------------------------------------------------------------ directory pages
def eras_page():
    counts = {e: len(rs) for e, rs in era_records.items()}
    h = [head(ST("nav_eras", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("eras_h1")}</h1>')
    h.append(f'<div class="well"><h4>{L("eras_about_h")}</h4><p>{L("eras_about_p", y0=years[0], y1=years[1])}</p></div>')
    for e in eras_data:
        key = e["era_key"]
        n = counts.get(key, 0)
        link = f'<a href="era/{era_slug[key]}-1.html">{L("browse_era_link")}</a>' if n and key in era_slug else ""
        h.append(f'<div class="card"><div class="meta">{L("period_label")}: {esc(e.get("years") or "")} &middot; {n} {L("articles_word")}</div>'
                 f'<h2 style="font-size:19px;margin:4px 0 6px">{Lp(e.get("title_en") or "", e.get("title_es") or "")}</h2>'
                 f'<p>{Lp(e.get("summary_en") or "", e.get("summary_es") or "")}</p>{link}</div>')
    if LATER_ERA in era_records:
        rs = era_records[LATER_ERA]
        h.append(f'<div class="card"><div class="meta">{L("period_label")}: {esc(era_years(LATER_ERA))} &middot; {len(rs)} {L("articles_word")}</div>'
                 f'<h2 style="font-size:19px;margin:4px 0 6px">{era_pair(LATER_ERA)}</h2>'
                 f'<p>{era_summary_pair(LATER_ERA)}</p><a href="era/{era_slug[LATER_ERA]}-1.html">{L("browse_era_link")}</a></div>')
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def papers_page():
    h = [head(ST("nav_papers", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("papers_h1")}</h1>')
    h.append(f'<p>{L("papers_intro")}</p>')
    h.append('<div class="dirlist">')
    for p in papers:
        rs = paper_records[p]
        lccns = sorted({corpus[r["id"]]["lccn"] for r in rs if r["id"] in corpus and corpus[r["id"]]["lccn"]})
        places_ = sorted({r["place"] for r in rs if r["place"]})
        lccn_line = f'<span class="catnum">{L("lccn_label")} {esc(", ".join(lccns))}</span><br>' if lccns else ""
        h.append(f'<div><a href="paper/{paper_slug[p]}-1.html"><b>{esc(p)}</b></a> ({len(rs)})<br>'
                 f'{lccn_line}{esc("; ".join(places_))} &middot; {rs[0]["date"][:4]}-{rs[-1]["date"][:4]}</div>')
    h.append('</div></div>')
    h.append(FOOT)
    return "".join(h)

def topics_page():
    h = [head(ST("nav_topics", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("topics_h1")}</h1><p>{L("topics_intro")}</p><div class="dirlist">')
    for t in sorted(topics_all, key=lambda t: TOPIC_LABELS[t][0]):
        h.append(f'<div><a href="topic/{topic_slug[t]}-1.html"><b>{topic_label_pair(t)}</b></a> ({len(topic_records[t])})</div>')
    h.append('</div></div>')
    h.append(FOOT)
    return "".join(h)

def places_page():
    h = [head(ST("nav_places", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("places_h1")}</h1><div class="dirlist">')
    for pl in places_all:
        h.append(f'<div><a href="place/{place_slug[pl]}-1.html"><b>{esc(pl)}</b></a> ({len(place_records[pl])})</div>')
    h.append('</div></div>')
    h.append(FOOT)
    return "".join(h)

# ------------------------------------------------------------- misc section
KIND_STR = {"documents": "kind_documents", "listings": "kind_listings", "mail": "kind_mail"}
KIND_ORDER = ["documents", "listings", "mail"]

def misc_card(m, depth=0):
    p = "../" * depth
    lead = re.sub(r"\s+", " ", m["passage"]).strip()[:240]
    bits = [fmt_date(m["date"])]
    if m["place"]:
        bits.append(esc(m["place"]))
    return (f'<div class="card"><div class="meta">{" &middot; ".join(bits)}</div>'
            f'<h3><a href="{p}misc/{esc(m["id"])}.html">{esc(m["newspaper"])}</a></h3>'
            f'<p>{esc(lead)}&hellip;</p>'
            f'<p><span class="label kind">{L(KIND_STR[m["kind"]])}</span></p></div>')

def misc_index_page():
    h = [head(ST("nav_misc", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1>{L("misc_h1")}</h1>')
    h.append(f'<div class="card"><p>{L("misc_intro")}</p></div>')
    for kind in KIND_ORDER:
        items = [m for m in misc_items if m["kind"] == kind]
        if not items:
            continue
        h.append(f'<h2 style="margin-top:28px">{L(KIND_STR[kind])} ({len(items)})</h2>')
        h.append("".join(misc_card(m) for m in items))
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def misc_item_page(m):
    h = [head(m["newspaper"], depth=1), nav(depth=1), '<div class="wrap"><article class="page">']
    bits = [fmt_date(m["date"])]
    if m["place"]:
        bits.append(esc(m["place"]))
    h.append(f'<div class="meta">{" &middot; ".join(bits)}</div>')
    h.append(f'<h1>{esc(m["newspaper"])}</h1>')
    h.append(f'<p><span class="label kind">{L(KIND_STR[m["kind"]])}</span></p>')
    src = f'<div class="src">{L("source_label")}: {esc(m["newspaper"])}'
    if m["place"]:
        src += f' &middot; {esc(m["place"])}'
    src += f' &middot; {fmt_date(m["date"])}'
    if m["source_url"]:
        src += f'<br><a href="{esc(m["source_url"])}">{esc(m["source_url"])}</a>'
    h.append(src + "</div>")
    h.append(f'<div class="well"><h4>{L("misc_passage_h")}</h4>{paras(m["passage"])}</div>')
    yr = esc(m["date"][:4])
    if m["source_url"]:
        cite = (f'{esc(m["newspaper"])}. ({yr}). {esc(m["place"])}, {esc(m["date"])}. '
                f'US/DR Newspaper Timeline, Miscellaneous. Library of Congress, Chronicling America: {esc(m["source_url"])}')
    else:
        cite = f'{esc(m["newspaper"])}. ({yr}). {esc(m["date"])}. US/DR Newspaper Timeline, Miscellaneous.'
    h.append(f'<div class="well"><h4>{L("cite_h")}</h4><p>{cite}</p></div>')
    fake = {"id": m["id"], "newspaper": m["newspaper"], "date": m["date"]}
    h.append(observe_box(fake, f'misc/{m["id"]}.html'))
    h.append("</article></div>")
    h.append(FOOT)
    return "".join(h)

# ------------------------------------------------------------------- method
def method_page():
    main_end = max((r["date"][:4] for r in records if r["era"] != LATER_ERA), default=years[1])
    fmt = dict(n=len(records), p=len(papers), y0=years[0], y1=years[1], y1_main=main_end)
    h = [head(ST("nav_method", "es")), nav(), '<div class="wrap"><article class="page">']
    h.append(f'<h1>{L("method_h1")}</h1><div class="body">')
    h.append(f'<p>{L("method_p1", **fmt)}</p>')
    for hk, pk in (("method_p2_h", "method_p2"), ("method_p3_h", "method_p3"),
                   ("method_p4_h", "method_p4"), ("method_p5_h", "method_p5"),
                   ("method_p6_h", "method_p6")):
        body = L(pk, **fmt) if pk == "method_p4" else L(pk)
        h.append(f'<p><b>{L(hk)}</b> {body}</p>')
    h.append("</div></article></div>")
    h.append(FOOT)
    return "".join(h)

def notfound_page():
    h = [head(ST("notfound_h", "es")), nav(), '<div class="wrap">']
    h.append(f'<h1 style="margin-top:24px">{L("notfound_h")}</h1>')
    h.append(f'<p>{L("notfound_p")}</p>')
    h.append(f'<p><a href="index.html">{L("notfound_home")}</a></p>')
    h.append("</div>")
    h.append(FOOT)
    return "".join(h)

def llms_txt():
    return f"""# US/DR Newspaper Timeline (xmella.me/us-dr-newspaper-timeline)

A bilingual (English/Spanish) collection of United States newspaper coverage of the Dominican Republic, {years[0]} to {years[1]}: {len(records)} articles from {len(papers)} newspapers, presented in the order they were published. Most articles come from the Library of Congress's Chronicling America archive; a small number come from newspapers.com and say so on their pages. Some articles are reproduced in full; the rest carry a labeled summary and the passage it was written from. A Miscellaneous section holds documents, sailing directories, and mail tables printed alongside the news.

## How to cite an article
Name the newspaper and its date, link to the article's page on this site, and link to the original newspaper page at the Library of Congress (each article page carries that link). Example: The New York Herald, April 28, 1844, as presented at xmella.me/us-dr-newspaper-timeline, original at the Library of Congress, Chronicling America.

## En español
Una colección bilingüe (inglés/español) de la cobertura de la República Dominicana en los periódicos de Estados Unidos, de {years[0]} a {years[1]}: {len(records)} artículos de {len(papers)} periódicos, presentados en el orden en que se publicaron. La mayoría viene del archivo Chronicling America de la Biblioteca del Congreso; unos pocos vienen de newspapers.com y lo dicen en sus páginas. Para citar un artículo: nombre el periódico y su fecha, enlace a la página del artículo en este sitio y a la página original en la Biblioteca del Congreso.
"""

def sitemap(paths):
    items = "".join(f"<url><loc>{SITE_BASE}{esc(p)}</loc></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'

# -------------------------------------------------------------------- gates
def run_gates(files):
    """The v5 gates. Any failure is listed and fails the build."""
    from html import unescape
    failures = []
    # gate 3: every STR key and topic label has both languages
    for k, (en, es) in STR.items():
        if not (en or "").strip() or not (es or "").strip():
            failures.append(f"gate3: STR key '{k}' is missing a language")
    for k, (en, es) in TOPIC_LABELS.items():
        if not en.strip() or not es.strip():
            failures.append(f"gate3: topic '{k}' is missing a label")
    for t in topics_all:
        if t not in TOPIC_LABELS:
            failures.append(f"labels: topic key '{t}' in the data has NO label (unmapped keys fail the build)")
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
        # gate 2: no raw topic key where taxonomy renders. Keys with an
        # underscore are machinery-shaped and are forbidden in ALL visible
        # text. The three single-word keys (immigration, emigration,
        # unclassified) are also ordinary English words that occur inside
        # article prose, so for those the gate checks the taxonomy
        # surfaces themselves: pills, chips, headings, options.
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
        # gate 4: no stale coverage literals in chrome
        if "1820–1963" in content or "1,418" in content:
            failures.append(f"gate4 {path}: stale coverage literal ('1820–1963' or '1,418')")
        # gate 5: every relative href resolves to a generated file
        base_dir = os.path.dirname(path)
        for hm in re.finditer(r'href="([^"]*)"', noscript):
            href = hm.group(1)
            if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target:
                continue
            resolved = os.path.normpath(os.path.join(base_dir, target)).replace(os.sep, "/")
            if resolved not in files:
                failures.append(f"gate5 {path}: dead internal link '{href}' -> '{resolved}'")
    # gate 6: every search-index id has an article page
    idx = json.loads(files["assets/search-index.json"])
    for row in idx:
        if f"articles/{row['i']}.html" not in files:
            failures.append(f"gate6: search-index id '{row['i']}' has no article page")
    return failures

# --------------------------------------------------------------------- main
def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    for d in ["articles", "era", "paper", "topic", "place", "misc", "assets"]:
        os.makedirs(os.path.join(OUT, d))
    files = {}
    files["assets/style.css"] = CSS
    for i, r in enumerate(records):
        prev_r = records[i - 1] if i > 0 else None
        next_r = records[i + 1] if i < len(records) - 1 else None
        files[f'articles/{r["id"]}.html'] = article_page(r, prev_r, next_r)
    files["index.html"] = index_page()
    files["eras.html"] = eras_page()
    files["method.html"] = method_page()
    files["papers.html"] = papers_page()
    files["topics.html"] = topics_page()
    files["places.html"] = places_page()
    files["misc.html"] = misc_index_page()
    files["404.html"] = notfound_page()
    for rel, html in era_pages().items():
        files[rel] = html
    for rel, html in facet_pages().items():
        files[rel] = html
    for m in misc_items:
        files[f'misc/{m["id"]}.html'] = misc_item_page(m)
    files["assets/search-index.json"] = search_index()
    files["llms.txt"] = llms_txt()
    site_paths = [p for p in files if p.endswith(".html") and p != "404.html"]
    files["sitemap.xml"] = sitemap(site_paths)
    files["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}sitemap.xml\n"
    for rel, content in files.items():
        with open(os.path.join(OUT, rel), "w", encoding="utf-8") as f:
            f.write(content)
    # workshop artifact (not published): the summary regeneration queue
    with open(os.path.join(BASE, "data/summary-regeneration-queue.json"), "w", encoding="utf-8") as f:
        json.dump({"withheld_failed_fidelity_check": sorted(QUARANTINE),
                   "flagged_window_bleed_screen": sorted(FLAG_BLEED - QUARANTINE)}, f, indent=1)
    by_source = {}
    for r in records:
        by_source[r["source_tag"]] = by_source.get(r["source_tag"], 0) + 1
    print(f"v5 built: {len(records)} records {by_source}, {n_full} full text, "
          f"{STRIPPED} headline repeats stripped, {len(QUARANTINE)} summaries withheld, "
          f"{len(misc_items)} misc items, {len(files)} files total")
    failures = run_gates(files)
    if failures:
        print(f"\nGATES FAILED ({len(failures)}):")
        for f_ in failures[:60]:
            print("  -", f_)
        sys.exit(1)
    print("gates: all 6 pass (attributes clean, no raw keys in visible text, "
          "STR complete, no stale literals, no dead internal links, search index matches pages)")

if __name__ == "__main__":
    main()
