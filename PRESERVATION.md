# Preservation package - US/DR Newspaper Timeline (OAIS-lite)

Adopted with the adversarial review rebuild spec, item 10 (2026-11-01).

## The package
The preservation copy of this edition is the combination of:
1. The raw Library of Congress OCR page-text archive (the Drive
   folder's chronam_dominican_republic/ tree), the source every
   excerpt and digest traces to.
2. The classified corpus: handoff/full records.jsonl (51,008 records)
   and full_timeline_records.jsonl, with their SHA-256 provenance.
3. The curated timeline data (bundle timeline.json) and this project's
   extraction rows (data/extraction*.jsonl) - the article texts.
4. The build inputs and generator (scripts/build_pilot.py) and the
   design/product truths (DESIGN.MD, PRODUCT.md, PROJECT-RULES.md).
5. The adversarial review and its evidence (review/), preserved as
   the edition's QA record.

## Conventions a future verifier must know
- Raw archive file names are sha256(source_url) - an ADDRESSING
  convention, not content hashes. The content digest of a page's OCR
  text is the record's source_text_sha256; the digest of the located
  passage is excerpt_sha256, reproducible from the passage displayed
  on each article page (the v3 build gates on this: 1,418/1,418).
- The bundle's eras.json counts are WRONG in 6 of 10 eras and are
  superseded; all counts are recomputed from the records at build.
- records.json's `title` field is deprecated (see SCHEMA.md).

## Snapshot rule
After any ship that changes data or generator, snapshot the package
off-repo (Drive project folder) with a manifest of file hashes.
The GitHub repo is the publication surface, not the archive.
