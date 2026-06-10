# Label test corpus

A small, labelled set of synthetic alcohol labels that drives the extractor,
verification, and performance tests. Each case bundles:

- **`application`** — the *expected* COLA data (TTB 5100.31 / 1513-0020), keyed
  to the `Application` ORM columns.
- **`label`** — what is physically *printed* on the rendered image. This is the
  ground truth the OCR extractor must recover; in the fault cases it differs
  from `application` on purpose.
- **`golden`** — the verdict the verification engine should produce: an overall
  roll-up, a per-field verdict (`match` / `soft_warning` / `mismatch`), and the
  special government-warning result (`compliant` / `altered` / `missing`).

## Cases

| id | scenario | overall | drawn from |
| --- | --- | --- | --- |
| `old_tom_clean_pass` | distilled spirits, all fields match | pass | brief's OLD TOM example |
| `coastal_vines_wine_pass` | imported wine (vintage, country) | pass | breadth (2nd product type) |
| `stones_throw_case_diff` | brand differs only by letter case | warning | Dave's "STONE'S THROW" |
| `abv_mismatch` | label ABV ≠ application ABV | fail | common data-entry error |
| `altered_warning_titlecase` | warning in title case, not all caps | fail | Jenny's real catch |
| `missing_warning` | mandatory warning absent | fail | required-element check |

The set spans every verdict state: pass / warning / fail overall; match /
soft-warning / mismatch per field; compliant / altered / missing warning.

## Layout

```
corpus/
├── schema.py        # typed shapes + enums + (de)serialisation
├── cases.py         # CASES — the source of truth
├── generate.py      # renders images + writes manifest.json
├── manifest.json    # committed, derived from cases.py
├── images/*.png     # committed rendered labels
└── README.md
```

## Usage

```python
from tests.corpus import load_corpus

for case in load_corpus().cases:
    img = case.image_path()          # rendered label PNG
    expected = case.application      # what the agent filed
    golden = case.golden             # verdict the engine should return
```

## Regenerating

`manifest.json` is derived from `cases.py`, and a test fails if they drift. After
editing cases, regenerate from the `backend/` directory:

```bash
python -m tests.corpus.generate
```

This re-renders the PNGs (Pillow, a dev-only dependency) and rewrites the
manifest. The images are committed so the test suite never needs Pillow or
system fonts at test time.
