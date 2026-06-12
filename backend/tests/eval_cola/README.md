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

Scraped 2026-06-10. **Image-set completeness re-verified 2026-06-11**: every
case's image count was checked against the live registry's attachment list
(`publicFormDisplay` per TTB ID) — all 30 match, so the 14 single-image cases
really are single-image filings (can wraps / keg collars where one artwork is
the whole label set), not partial scrapes. Each case is traceable: the TTB ID
in the filename/manifest resolves at
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

Measured accuracy (2026-06-11, after the adaptive rescue passes): brand 29/30,
**ABV 30/30, net contents 27/28, government warning 29/30** — up from
29/23/26/10 in the first measurement the same day. The gains came from three
changes, each driven by a failure family this eval surfaced:

- **Rotation rescue** (`app/verify/pipeline.py`): when the warning (or a field)
  is unrecovered, the image is re-OCR'd at ±90° and per-field best verdicts
  merged — can wraps and keg collars print across the artwork.
- **Warning zoom rescue** (same module): the warning region, located by its
  header, is cropped + upscaled and re-read — the statement is the smallest
  print on the label and the detector drops lines at native resolution.
- **Fragmented-read word coverage** (`app/verify/warning.py`): justified
  columns and curved collars scramble OCR reading order; when the sequence
  checks fail but *every* word of the statement was read, the wording is
  verified word-by-word (tampering removes words, so it still fails).
- **Extractor robustness** (`app/extract/extractors.py`): `I3%`→`13%` digit
  confusion, `ABV`/`ALCOHOLBYVOLUME` anchors, a big "50" next to a small
  "ALC/VOL" caption assembled across lines, and proof→ABV derivation
  (80 PROOF pins 40%).

One annotation fix the rescue passes exposed (2026-06-11): Coyote Dawn's
`label_truth` said 45 % / 90 proof, but the zoomed crop plainly prints
"40% Alc by Vol / 80 PROOF" — the manual annotation was a misread; corrected
in `manifest.json` (note kept in its `notes`).

## Known gaps this set exposed (by design, kept honest)

- **Leinenkugel's keg cap (warning `missing`, net contents `mismatch`)**: the
  text follows the cap's printed **arc**, every word at a different angle.
  Flat circular collars are now handled by the **arc rescue**
  (`app/verify/pipeline.py`: Hough-detect the collar's circle, polar-unwrap
  around it, verify over the union of the unwrapped reads) — verified against
  a real Stillwater keg collar. Leinenkugel's specifically remains open: it is
  a *photograph of a cone*, so the printed curve is a perspective-distorted
  ellipse with no detectable circle center. Needs perspective rectification
  first — tracked as a follow-up.
- One brand mismatch: Giro Splendido's script logotype on a blue keg collar
  (no OCR-recoverable text in the logotype; it lands in review, not auto-pass).
