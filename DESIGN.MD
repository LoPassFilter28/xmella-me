# DESIGN.MD - US/DR Newspaper Timeline (at xmella.me/us-dr-newspaper-timeline/)

xmella.me is PiK0's portfolio domain; this project is a branch on it.
The pilot deploys under /us-dr-newspaper-timeline/ so the domain root
stays free for the future portfolio home (not planned yet, per PiK0).

Status: PLANNING DRAFT, 2026-11-01. Written before any page exists, per the
407 FYI procedure (DESIGN.MD first). PiK0's decisions govern; Antigravity's
bundle design system is source material, reconciled below. Open items are
listed at the end and need PiK0's ruling before build.

## Governing decisions (PiK0, 2026-11-01)
- Color scheme: **Parchment & Ink** (picked over the bundle's palette).
- Format basis: the GEN1011 assignment submitted to Professor Schneider -
  per-article treatment: name + source URL, prose, images with source
  URLs, citations/references. Segoe UI.
- Bilingual EN/ES is native (PROJECT-RULES.md). Evidence labels on every
  claim: Documented vs Oral tradition / loosely verified.
- Stack: GitHub repo -> Vercel -> Cloudflare DNS. Project rules live in
  PROJECT-RULES.md; this file holds design tokens and layout law only.

## Color tokens (Parchment & Ink, governing)
| Token | Value | Role |
|---|---|---|
| --parchment | #F7F2E7 | Primary canvas |
| --parchment-elevated | #FCF9F1 | Cards, article surfaces (derived, one step up) |
| --parchment-muted | #EDE4D0 | Wells, filter bars, transcript backgrounds (derived) |
| --ink | #1C1A17 | Primary text, masthead |
| --ink-secondary | #4C463C | Datelines, metadata (derived) |
| --ink-muted | #7A7263 | Hashes, counters, captions (derived) |
| --oxblood | #7A2E2E | Primary accent: active states, seals, links emphasis |
| --slate | #33526B | Secondary accent: source links, diplomatic/document markers |
| --border | #D8CCB2 | Card borders, column rules (derived) |
| --border-strong | #A08D6B | Masthead double rules, ledger frames (derived) |

### Reconciliation with the bundle palette
Antigravity's system (#f5efe4 parchment, #8b261d crimson, #b8860b brass,
#1d3557 navy) maps onto the picked scheme role-for-role: crimson's role is
played by oxblood, navy's by slate, brass is DROPPED (no token in the
picked scheme; maritime/document seals take oxblood, source markers take
slate). Their "Microfilm Vault" dark mode is carried as an UNDECIDED
variant (open item 2); if adopted, its tokens derive from the table above
inverted, not from their hex values.

## Typography
- System family: **Segoe UI** (assignment basis) where the device has it
  (Windows). Segoe UI does not exist on macOS/iOS/Android and cannot be
  embedded as a webfont (Microsoft proprietary), so the embedded baseline
  is **Source Sans 3** (open humanist sans, same design family spirit),
  loaded as a webfont on every page; stack: "Segoe UI", "Source Sans 3",
  -apple-system, sans-serif. AMENDED 2026-11-01 after PiK0 caught that
  the pilot rendered in fallback fonts on his phone: a named font that
  never renders is not a type system. Body 15-16px / 1.65 for article
  prose and summaries; UI controls 13-14px, weight 600 for pills/tabs.
- Monospace for provenance: "JetBrains Mono", Consolas, monospace -
  record ids, SHA-256 digests, verbatim transcript wells.
- DECIDED (PiK0, 2026-11-01): Segoe UI throughout. The bundle's Playfair
  Display display serif is NOT adopted; weight, size, and the double-rule
  masthead carry the broadsheet character.

## Browsing rule (PiK0 order, 2026-11-01)
No page ever renders the whole collection. The timeline index is a
directory + search (results capped at 50 rendered at a time, data loaded
lazily as a compact JSON index); browsing runs through era pages of at
most 100 records with pagers. The first pilot shipped all 1,418 cards in
one 3.4 MB page; PiK0's verdict ("mentally insane") is the standing
precedent: a data dump is not a finding aid.

## Information architecture (provisional until the full-bundle audit)
The bundle's seven views are the starting IA: Curated Timeline (1,418),
Featured Documents, OCR Lab, Grey-Area Review, Maritime & Commodity
Listings, Historical Eras (10), Mella Maritime Clippings (9).
COUNTS WARNING: Documents/Grey/Listings at bundle scale (8,987 / 3,042 /
5,444) come from the 51,008-record corpus in the 95 MB full bundle, not
yet audited. The shipped IA and every count on the page are set only
after FULL-BUNDLE-AUDIT-PLAN.md runs. No count from the bundle docs is
published on trust.

## Article page format (Schneider basis, per record)
1. Headline/name line (faithful headline from extraction; never invented).
2. Source line: newspaper, place, date + the record's LOC source URL.
3. Prose treatment: the article text (extraction rows), faithful substance.
4. Image: the page scan or crop, with its source URL credited under it.
5. Provenance block: record id, SHA-256 digests, extraction status and
   confidence, evidence label where a claim needs one.
6. References: LOC citation for the page; bundle provenance where used.

## Card anatomy (timeline and index views)
Date badge, newspaper + place, headline, EN/ES summary (toggle switches
language site-wide without reload), topic pills, expandable excerpt,
source link, provenance digest in mono. Relevance/classification badge
per the timeline data.

## Bilingual presentation
EN/ES toggle in the masthead utility bar; every UI label, era narrative
and summary exists in both languages in the data (summary / summary_es).
No mixed-language pages: the toggle switches the whole surface, the same
discipline as the data model.

## Infrastructure hooks (values on file, not secret)
- Sentry project xmella-me, DSN in the activation checklist; error script
  in the page head at build.
- New Relic browser app xmella.me, applicationID 601689257; loader
  snippet values in the activation checklist; added at build.
- Imgbot attaches at repo creation; .imgbotconfig (min size threshold,
  schedule) committed with the first pass.
- Uptime monitor for xmella.me is created at launch (New Relic), cadence
  set by the then-current plan (free 500/mo until Student provisions).

## Ship gates (from PROJECT-RULES / 407 procedure)
Integrity sweep over generated pages (ids, links, digests) + browser
behaviour verification (toggle, filters, expansion actually working) +
BrowserStack real-device pass before the launch ship is called verified.
Text layout verified by stress measurement, not screenshots alone.

## Decided scope (PiK0, 2026-11-01)
- Microfilm Vault: DEFERRED to a post-launch phase, once the light
  design is proven. Tokens stay theme-ready from day one; deferral
  costs no rework.
- Launch scope: TIMELINE-FIRST PILOT. The pilot ships the Curated
  Timeline (1,418), the 10 Era chapters, and the 9 Mella Maritime
  clippings, on the audited 8 MB bundle data + our extraction rows.
  Article pages carry full text where extraction exists (104+ and
  growing as the lanes run); every other record carries its summary,
  excerpt, and LOC source link.
- SEQUENCE (PiK0's order): deploy the pilot FIRST; then a review and
  confirmation session with PiK0; only AFTER that confirmation do we
  dig through the full Antigravity corpus (the 95 MB Drive folder,
  "the mess antigravity and the other agents left behind") under
  FULL-BUNDLE-AUDIT-PLAN.md. The remaining views (Documents,
  Grey-Area, Listings) phase in only from that later audit.
