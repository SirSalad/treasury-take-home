"""Out-of-distribution OCR robustness eval over real bottle photos.

SCOPE: the product target is *pre-market COLA review*, whose input is the
bottler/importer's clean, head-on **label artwork** — exactly what the synthetic
golden corpus (``tests/corpus``, exercised by the unit suite) models, and the
representative measure of COLA correctness. This suite is deliberately the
opposite: messy, real **consumer/field bottle photos** (Jack Daniel's, US
beer/wine/spirits, wildly-colorful RTDs, and bad shots) that would *not* be filed
with the TTB. It is a robustness / graceful-degradation check, not a COLA-accuracy
measurement — it confirms the pipeline degrades sensibly on inputs outside its
intended distribution (brands still fuzzy-match, regulated fields read where
legible, and unreadable photos flag for retake rather than producing a confident
wrong verdict).

Marked ``eval`` and deselected by default; run it with ``pytest -m eval``.

For each case it asserts the *stable, reproducible* outcomes:
  * the image-quality grade (ok vs. low/retake),
  * that a readable brand verifies as match/soft-warning (not a false mismatch),
  * that the ABV is recovered where the label prints it legibly.

Each case's image is committed under ``tests/eval/images/`` (see
``images/ATTRIBUTION.md`` for source + licence), so the eval runs offline; the
``commons_file`` is only refetched (and cached under ``.cache``) if the committed
image is missing. A case whose image is unavailable is SKIPPED, not failed.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from app.api.schemas import ApplicationInput
from app.ocr.quality import assess_image_quality
from app.ocr.service import get_ocr_service
from app.verify.engine import verify_label
from app.verify.schemas import FieldStatus

pytestmark = pytest.mark.eval

_HERE = Path(__file__).parent
_CACHE = _HERE / ".cache"
_UA = {"User-Agent": "ttb-label-verify-ocr-eval/1.0 (research)"}


def _load_cases() -> list[dict]:
    return json.loads((_HERE / "manifest.json").read_text())["cases"]


def _fetch(commons_file: str) -> Path | None:
    """Resolve a Commons file to a cached local image, or ``None`` if offline."""
    _CACHE.mkdir(exist_ok=True)
    cached = _CACHE / (commons_file.replace(" ", "_").replace("'", "").replace(",", ""))
    if cached.exists() and cached.stat().st_size > 1024:
        return cached
    api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "titles": f"File:{commons_file}",
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1100,
            "format": "json",
        }
    )
    for attempt in range(3):
        try:
            meta = json.loads(
                urllib.request.urlopen(urllib.request.Request(api, headers=_UA), timeout=25).read()
            )
            info = next(iter(meta["query"]["pages"].values()))["imageinfo"][0]
            src = info.get("thumburl") or info["url"]
            data = urllib.request.urlopen(
                urllib.request.Request(src, headers=_UA), timeout=30
            ).read()
            cached.write_bytes(data)
            return cached
        except Exception:  # noqa: BLE001 — offline/rate-limited: skip, don't fail
            time.sleep(6 * (attempt + 1))
    return None


def test_ocr_robustness_out_of_distribution(capsys: pytest.CaptureFixture[str]) -> None:
    cases = _load_cases()
    ocr = get_ocr_service()

    rows: list[str] = []
    failures: list[str] = []
    skipped = 0
    scored = 0

    for case in cases:
        # Committed image first (offline); fall back to Commons only if missing.
        local = _HERE / case["image"]
        path = local if local.exists() else _fetch(case["commons_file"])
        if path is None:
            skipped += 1
            rows.append(f"  SKIP  {case['id']:26} (image unavailable)")
            continue

        result_ocr = ocr.extract(str(path))
        quality = assess_image_quality(result_ocr)
        expect = case["expect"]
        case_fail: list[str] = []

        # 1) image-quality grade
        if quality.level != expect["quality"]:
            case_fail.append(f"quality {quality.level}!={expect['quality']}")

        brand_status = None
        abv_status = None
        if expect.get("brand_status") or expect.get("abv_reads"):
            application = ApplicationInput(**case["ground_truth"])
            verdict = verify_label(application, result_ocr)
            by_field = {f.field: f.status for f in verdict.fields}
            brand_status = by_field.get("brand_name")
            abv_status = by_field.get("alcohol_content")

            # 2) a readable brand must verify as match/soft-warning (not a false mismatch)
            allowed = expect.get("brand_status")
            if allowed is not None:
                want = {FieldStatus(s) for s in allowed}
                if brand_status not in want:
                    case_fail.append(
                        f"brand {brand_status.value if brand_status else None} not in {allowed}"
                    )

            # 3) ABV recovered where the label prints it legibly
            if expect.get("abv_reads"):
                if abv_status is not FieldStatus.MATCH:
                    case_fail.append(f"abv {abv_status.value if abv_status else None}!=match")

        scored += 1
        mark = "FAIL" if case_fail else "ok  "
        chars = sum(len(line.text) for line in result_ocr.lines)
        brand_str = brand_status.value if brand_status else "-"
        abv_str = abv_status.value if abv_status else "-"
        detail = f"q={quality.level:<3} chars={chars:<3} brand={brand_str} abv={abv_str}"
        rows.append(f"  {mark}  {case['id']:26} [{case['category']:9}] {detail}")
        if case_fail:
            failures.append(f"{case['id']}: {', '.join(case_fail)}")

    report = "\n".join(
        [
            "",
            "=== OCR real-world eval ===",
            *rows,
            f"scored={scored} failed={len(failures)} skipped={skipped}",
            "",
        ]
    )
    with capsys.disabled():
        print(report)

    if scored == 0:
        pytest.skip("no eval images could be fetched (offline / rate-limited)")
    assert not failures, "OCR eval regressions:\n" + "\n".join(failures)
