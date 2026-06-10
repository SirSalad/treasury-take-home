"""In-distribution OCR eval over real COLA label artwork from the TTB registry.

Complements the two existing suites: ``tests/corpus`` is synthetic golden data
(exact verdicts, runs in the unit suite) and ``tests/eval`` is out-of-distribution
consumer bottle *photos* (robustness). This set is the real thing the product
will see: actual label artwork from 30 approved 2025–2026 COLAs, scraped from
the public registry (see ``README.md``), with the filed application data as
ground truth.

Expectations are **monotone**: ``manifest.json`` records the pipeline's observed
result per case (``expect``), and each assertion requires the current result to
be *at least as good* — better is a pass (and prints as ``BEAT``), worse is a
regression failure. This encodes today's known gaps honestly (rotated
government-warning text on can wraps reads as ``missing``; handwritten or
tiny-print ABV does not extract) without freezing them as a ceiling.

A case may have several label images (front/back/keg collar — TTB approves the
set); each is OCR'd independently and the best per-field outcome across the set
is scored, mirroring a reviewer who sees every affixed label.

Marked ``eval`` and deselected by default; run with ``pytest -m eval``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.schemas import ApplicationInput
from app.ocr.quality import assess_image_quality
from app.ocr.service import get_ocr_service
from app.verify.engine import verify_label

pytestmark = pytest.mark.eval

_HERE = Path(__file__).parent

# Lower rank is better; assertions require rank(actual) <= rank(expected).
_QUALITY_RANK = {"ok": 0, "low": 1, "retake": 2}
_FIELD_RANK = {"match": 0, "soft_warning": 1, "mismatch": 2, None: 3}
_WARNING_RANK = {"compliant": 0, "altered": 1, "missing": 2}


def _best(values: list[str | None], rank: dict) -> str | None:
    present = [v for v in values if v is not None]
    return min(present, key=lambda v: rank[v]) if present else None


def test_cola_registry_artwork() -> None:
    manifest = json.loads((_HERE / "manifest.json").read_text())
    ocr = get_ocr_service()

    rows: list[str] = []
    failures: list[str] = []

    for case in manifest["cases"]:
        reg = case["registry"]
        truth = case["label_truth"]
        application = ApplicationInput(
            brand_name=reg["brand_name"],
            product_type=case["product_type"],
            class_type=reg["class_type"],
            alcohol_content_pct=truth["alcohol_content_pct"],
            net_contents=truth["net_contents"],
            vintage=truth["vintage"],
            fanciful_name=reg["fanciful_name"],
        )

        qualities: list[str] = []
        brands: list[str | None] = []
        abvs: list[str | None] = []
        warnings: list[str] = []
        for img in case["images"]:
            result = ocr.extract(str(_HERE / img["file"]))
            qualities.append(assess_image_quality(result).level)
            verdict = verify_label(application, result)
            by_field = {f.field: f.status.value for f in verdict.fields}
            brands.append(by_field.get("brand_name"))
            abvs.append(by_field.get("alcohol_content"))
            warnings.append(verdict.government_warning.verdict.value)

        got = {
            "quality_best": _best(qualities, _QUALITY_RANK),
            "brand_at_least": _best(brands, _FIELD_RANK),
            "abv_at_least": _best(abvs, _FIELD_RANK),
            "warning_at_least": _best(warnings, _WARNING_RANK),
        }
        expect = case["expect"]

        case_fail: list[str] = []
        beat: list[str] = []
        for key, rank in (
            ("quality_best", _QUALITY_RANK),
            ("brand_at_least", _FIELD_RANK),
            ("abv_at_least", _FIELD_RANK),
            ("warning_at_least", _WARNING_RANK),
        ):
            got_rank = rank.get(got[key], max(rank.values()))
            want_rank = rank.get(expect[key], max(rank.values()))
            if got_rank > want_rank:
                case_fail.append(f"{key}: {got[key]} worse than {expect[key]}")
            elif got_rank < want_rank:
                beat.append(f"{key}: {got[key]} (was {expect[key]})")

        mark = "FAIL" if case_fail else ("BEAT" if beat else "ok  ")
        rows.append(
            f"  {mark}  {case['ttbid']} [{case['category']:7}] "
            f"{reg['brand_name'][:24]:24} q={got['quality_best']:<3} "
            f"brand={got['brand_at_least'] or '-':<12} "
            f"abv={got['abv_at_least'] or '-':<12} "
            f"warn={got['warning_at_least']}"
        )
        if case_fail:
            failures.append(f"{case['ttbid']} ({reg['brand_name']}): " + "; ".join(case_fail))

    print("\n".join(["", "=== COLA registry artwork eval ===", *rows, ""]))
    assert not failures, "COLA eval regressions:\n" + "\n".join(failures)
