# Record schema - Dublin Core minimum mapping

Adopted with the adversarial review rebuild spec, item 10 (2026-11-01).
The timeline records already carry nearly all of the Dublin Core
minimum; this maps the fields so any future builder (or the corpus
phase-in) uses them consistently. Article pages emit the core terms
as DC meta tags.

| DC term | Record field | Notes |
|---|---|---|
| identifier | id (e.g. cr16964-1) | Stable record id; printed on every page |
| title | headline_as_printed (extracted records only) | Never invented; unextracted records have no verified headline |
| publisher | newspaper | Title string as printed in LOC metadata |
| contributor / coverage | place | Place of publication as LOC gives it |
| date | date (ISO) | Issue date; population-verified 1,418/1,418 |
| source | source_url | LOC viewer page; derived addressing, link sweep standing |
| identifier (digest) | excerpt_sha256, source_text_sha256 | Passage digest is reproducible from the displayed passage |
| type | content_type | text / document-like classes from the corpus screen |
| language | summary EN/ES; article language as printed | Bilingual edition layer over the source |
| subject | topics[] | Corpus topic screen; facets expose these as the topic index |
| relation | era | Editorial periodization; labeled as period, not coverage |
| rights / evidence | evidence class | Documented vs Oral tradition / loosely verified (PROJECT-RULES) |

## Deprecated field warning
records.json's `title` field is NOT a headline: in ~65% of records it
is a mid-article OCR fragment and in ~35% the head of the summary
(adversarial review, Front 6). The pilot ignores it. Do not build on
it; a future dataset revision should rename it `title_unverified` or
drop it.

## Classification warning
The corpus `relevance` label is a keyword screen (measured ~85%
strict precision inside the curated timeline, ~70% in the wider
pool). It is a discovery aid, never an import key. The grey pool is
quarantined pending measured human review per tranche.
