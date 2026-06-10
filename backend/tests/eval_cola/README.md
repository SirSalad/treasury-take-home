# Real COLA artwork eval (TTB Public COLA Registry)

Thirty approved 2025–2026 COLAs pulled from the [TTB Public COLA
Registry](https://ttbonline.gov/colasonline/publicSearchColasBasic.do) — ten
each wine / distilled spirits / malt beverage — with the **actual label
artwork** filed with each application. Unlike the synthetic golden corpus
(`tests/corpus`) and the out-of-distribution bottle *photos* (`tests/eval`),
this set is exactly the product's intended input: clean, head-on label artwork
attached to a TTB form 5100.31.

Run it with:

```bash
pytest -m eval tests/eval_cola
```

## How the set was built

1. Advanced registry search, date completed 2024–2026, TTB IDs restricted to
   2025+ receipts (the first five digits of a TTB ID encode the receipt date),
   class types 80/81/84 (wine), 101/166/170/198/943 (spirits),
   901/902/950/951/952 (malt). First results page per product type,
   de-duplicated by brand — no other selection, so the set includes whatever
   the registry happened to contain: handwritten keg collars, rotated can
   wraps, a photographed keg disc, a genuine 3 % lager.
2. For each COLA, the printable form page (`viewColaDetails.do?action=
   publicFormDisplay`) was captured: the filed fields verbatim
   (`registry` in `manifest.json`) and every label-image attachment
   (`images/<ttbid>_<n>.jpg`, transcoded to JPEG, max side 1600 px).
3. The current 5100.31 revision **no longer carries ABV or net-contents
   fields**, so those were annotated manually (`label_truth`) by reading the
   full-resolution artwork, with zoomed crops for small or rotated text.

Scraped 2026-06-10. Each case is traceable: the TTB ID in the filename/manifest
resolves at
`https://ttbonline.gov/colasonline/viewColaDetails.do?action=publicDisplaySearchAdvanced&ttbid=<ttbid>`.
COLA filings are public records published by the U.S. Treasury (TTB); the set
is used here as test data with full attribution via TTB IDs.

## What the eval asserts

`expect` per case records the pipeline's result when the set was built, and
`test_cola_eval.py` asserts **monotonically**: equal or better passes (better
prints as `BEAT`), worse fails. A case with several label images scores the
best per-field outcome across the set, mirroring a reviewer who sees every
affixed label.

Observed baseline (2026-06-10): quality `ok` 30/30, brand `match`/
`soft_warning` 29/30, ABV `match` 23/30, government warning found 10/30.

## Known gaps this set exposed (by design, kept honest)

- **Rotated text is the big one.** On real can wraps and keg collars the
  Government Warning usually runs 90° to the artwork; the OCR pipeline does
  not detect rotated lines, so the warning scores `missing` on 20/30 cases
  despite being present on every label. Tracked as a follow-up issue.
- **Handwritten/photographed labels**: two keg collars (Beach Ball, Schnucki —
  the latter a literal photo of a handwritten disc) defeat ABV extraction.
- **Tiny edge print**: ABV in ~6 pt rotated type at the label margin
  (Anthony's) or dense small print (Benchmark) does not extract.
- One brand mismatch: Giro Splendido's script logotype on a blue keg collar.
