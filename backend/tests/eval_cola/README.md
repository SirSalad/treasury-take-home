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

## What the eval asserts — golden correctness

These are real, **correctly-filed** COLAs: the filed application agrees with
what's printed, so a perfect tool should verify every field. `golden` per case
records that **correct verdict per field** (the ground truth), and
`test_cola_eval.py` scores the pipeline **true/false against it** — not against
the pipeline's own past output. A `brand_name` golden of `match`/`soft_warning`
both mean "brand verified" (case/form aside); the others are exact. Each case is
scored on the **best verdict across its full set of label images**, because a
COLA submission is the set of affixed labels (warning on the back, ABV on the
front, …).

The eval **surfaces every failing label** in a printed scorecard — it does not
hide OCR limits behind monotone baselines — and asserts per-field **accuracy
floors** (a ratchet): the pipeline can't regress, and you raise the floors in
`test_cola_eval.py` as OCR improves. The gap between the floors and 30/30 is the
continuous-improvement backlog.

Measured accuracy (2026-06-11): brand 29/30, ABV 23/30, net contents 26/28,
**government warning 10/30** — the warning on tightly-kerned/rotated labels is
the standout gap to drive up next.

## Known gaps this set exposed (by design, kept honest)

- **Government Warning (10/30) is the big one.** It's present and standard on
  every label, but on real can wraps and keg collars it runs 90° to the artwork
  (OCR doesn't detect rotated lines → `missing`), and where it is read, OCR
  noise on the long statement drops the wording similarity below threshold
  (→ `altered`). Tracked as a follow-up issue.
- **Handwritten/photographed labels**: two keg collars (Beach Ball, Schnucki —
  the latter a literal photo of a handwritten disc) defeat ABV extraction.
- **Tiny edge print**: ABV in ~6 pt rotated type at the label margin
  (Anthony's) or dense small print (Benchmark) does not extract.
- One brand mismatch: Giro Splendido's script logotype on a blue keg collar.
