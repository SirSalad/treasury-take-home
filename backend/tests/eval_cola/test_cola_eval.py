"""Golden correctness eval over real TTB COLA labels.

Each case is a real, correctly-filed COLA: the filed application agrees with
what is printed, so a perfect tool should verify every field. ``manifest.json``
records that correct verdict per field in ``golden`` — the ground truth the
pipeline is scored **true/false** against, not the pipeline's own past output.

Each case is verified through the production multi-image path
(:func:`app.verify.pipeline.verify_label_images`): the case's full set of label
images is read and merged on best verdict per field, because a COLA submission
is the set of affixed labels (the Government Warning usually sits on the back
label, ABV on the front, …) and a reviewer sees them all. The eval and the API
share this code path, so the measured accuracy is the product's accuracy.

This is the honest accuracy measure on real data: it does **not** hide OCR
limitations behind monotone baselines. The test prints a full scorecard listing
every failing label, and asserts per-field **accuracy floors** — a ratchet, so
the pipeline cannot regress and the team raises the bar as OCR improves. The
gap between the floors and 30/30 is the continuous-improvement backlog (today:
one arc-curved keg cap that defeats straight-line OCR — its warning and net
contents — and one script-font brand logotype).

Marked ``eval`` and deselected by default; run with ``pytest -m eval``.
"""

from __future__ import annotations

import pytest

from app.api.schemas import ApplicationInput
from app.ocr.service import get_ocr_service
from app.pool import COLA_GOLDEN, pool_images, records_for
from app.verify.pipeline import verify_label_images

pytestmark = pytest.mark.eval


def _cola_cases() -> list[dict]:
    """The real-COLA golden cases as a filtered view over the canonical pool.

    Each ``cola_golden`` pool record is projected back to the case shape this
    eval scores against (registry / label_truth / golden / images), so the
    measured accuracy is identical to scoring the legacy manifest — only the
    data *source* moved into the shared pool.
    """
    images = pool_images()
    cases: list[dict] = []
    for record in records_for(COLA_GOLDEN):
        golden = record["cola_golden"]
        cases.append(
            {
                "ttbid": record["provenance"]["ttbid"],
                "category": golden["category"],
                "registry": golden["registry"],
                "label_truth": golden["label_truth"],
                "golden": golden["golden"],
                "product_type": golden["product_type"],
                "images": [str(images / name) for name in record["images"]],
            }
        )
    return cases


# Minimum number of cases the pipeline must verify correctly per field — the
# current measured accuracy. Raise these as OCR improves; never lower them.
# Denominators: brand 30, alcohol 30, net_contents 28, government_warning 30.
_ACCURACY_FLOORS = {
    "brand_name": 29,
    "alcohol_content": 30,
    "net_contents": 27,
    "government_warning": 29,
}


def _field_ok(field: str, golden: str, actual: str) -> bool:
    # A correctly-filed brand is "verified" whether the pipeline calls it an exact
    # match or flags a case/form difference; only failing to find it is wrong.
    if field == "brand_name":
        return actual in ("match", "soft_warning")
    return actual == golden


def _application(case: dict) -> ApplicationInput:
    reg, truth = case["registry"], case["label_truth"]
    return ApplicationInput(
        brand_name=reg["brand_name"],
        product_type=case["product_type"],
        class_type=reg["class_type"],
        alcohol_content_pct=truth["alcohol_content_pct"],
        net_contents=truth["net_contents"],
        vintage=truth.get("vintage"),
        fanciful_name=reg.get("fanciful_name"),
    )


def test_cola_golden_accuracy() -> None:
    cases = _cola_cases()
    ocr = get_ocr_service()

    totals: dict[str, int] = {}
    passes: dict[str, int] = {}
    rows: list[str] = []
    failures: list[str] = []

    for case in cases:
        application = _application(case)
        verdict, _ = verify_label_images(application, case["images"], ocr=ocr)

        by_field = {f.field: f.status.value for f in verdict.fields}
        actual = {
            "brand_name": by_field.get("brand_name", "absent"),
            "alcohol_content": by_field.get("alcohol_content", "absent"),
            "net_contents": by_field.get("net_contents", "absent"),
            "government_warning": verdict.government_warning.verdict.value,
        }

        marks: list[str] = []
        for field, golden in case["golden"].items():
            totals[field] = totals.get(field, 0) + 1
            if _field_ok(field, golden, actual[field]):
                passes[field] = passes.get(field, 0) + 1
                marks.append(f"{field}=ok")
            else:
                marks.append(f"{field}=FAIL({actual[field]}≠{golden})")
                failures.append(
                    f"{case['ttbid']} [{case['category']}] {field}: "
                    f"got {actual[field]}, golden {golden}"
                )
        ok = all("FAIL" not in m for m in marks)
        rows.append(
            f"  {'ok  ' if ok else 'FAIL'} {case['ttbid']} "
            f"[{case['category']:7}] {case['registry']['brand_name'][:22]:22} " + " ".join(marks)
        )

    scored = sum(totals.values())
    correct = sum(passes.values())
    report = [
        "",
        "=== Real COLA golden accuracy (best across all label images) ===",
        *rows,
        "",
        *[
            f"  {field:18} {passes.get(field, 0)}/{totals[field]}"
            f"  (floor {_ACCURACY_FLOORS[field]})"
            for field in sorted(totals)
        ],
        f"  OVERALL            {correct}/{scored}",
        "",
        f"  {len(failures)} field(s) below golden — the improvement backlog:",
        *[f"    - {f}" for f in failures],
        "",
    ]
    print("\n".join(report))

    # Ratchet: every field must meet its accuracy floor. Improvements are free;
    # regressions fail. Raise a floor here once a fix lifts the measured count.
    below = [
        f"{field}: {passes.get(field, 0)}/{totals[field]} < floor {floor}"
        for field, floor in _ACCURACY_FLOORS.items()
        if passes.get(field, 0) < floor
    ]
    assert not below, "Real-COLA accuracy regressed below the floor:\n" + "\n".join(below)
