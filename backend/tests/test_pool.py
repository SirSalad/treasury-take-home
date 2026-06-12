"""Integrity + parity tests for the canonical data pool (`app.pool`).

The pool is the single source of truth: the demo seeder and all three evals are
filtered views over it. These tests pin the per-use-case parity counts, assert
the data is internally consistent and self-contained (no consumer reads label
data from outside the pool), and guard the one upstream-authored view — the
synthetic corpus — against drift.
"""

from __future__ import annotations

import json
import os
from importlib import resources
from pathlib import Path

import pytest

from app.api.schemas import ApplicationInput
from app.models.application import Application
from app.pool import (
    BASE_SEED,
    COLA_GOLDEN,
    CORPUS_GOLDEN,
    OCR_STRESS,
    load_pool,
    pool_images,
    records_for,
)

# The agreed view sizes: real-COLA golden (30), OOD OCR stress (18), synthetic
# golden corpus (10), and the base demo set (7 = the 6 corpus reuses + jb_kirk).
_USE_CASE_COUNTS = {
    COLA_GOLDEN: 30,
    OCR_STRESS: 18,
    CORPUS_GOLDEN: 10,
    BASE_SEED: 7,
}
# Distinct records seeded live = sum of distinct records, with the 6 base/corpus
# reuses counted once: 30 + 18 + (10 corpus ∪ 1 base-only) = 59.
_TOTAL_RECORDS = 59
# Multi-image filings (real COLA front+back/neck sets).
_MIN_MULTI_IMAGE = 16

# Each annotation block is required exactly when its use-case tag is present.
_ANNOTATION_FOR = {
    COLA_GOLDEN: "cola_golden",
    OCR_STRESS: "ocr_expect",
    CORPUS_GOLDEN: "corpus_golden",
}


def test_per_use_case_counts() -> None:
    for use_case, expected in _USE_CASE_COUNTS.items():
        assert len(records_for(use_case)) == expected, use_case


def test_total_distinct_records() -> None:
    records = load_pool()
    assert len(records) == _TOTAL_RECORDS
    assert len({r["id"] for r in records}) == _TOTAL_RECORDS, "record ids must be unique"


def test_multi_image_coverage() -> None:
    multi = [r for r in load_pool() if len(r["images"]) > 1]
    assert len(multi) >= _MIN_MULTI_IMAGE


def test_every_record_image_is_present_and_non_trivial() -> None:
    images = pool_images()
    for record in load_pool():
        assert record["images"], f"{record['id']} has no images"
        for name in record["images"]:
            blob = (images / name).read_bytes()
            assert len(blob) > 1_000, f"suspiciously small pooled image: {name}"


def test_no_orphan_images_outside_referenced_set() -> None:
    """Every file in the pool image dir is referenced by some record (no cruft)."""
    referenced = {name for record in load_pool() for name in record["images"]}
    on_disk = {
        p.name
        for p in Path(str(pool_images())).iterdir()
        if p.is_file() and p.name != "ATTRIBUTION.md"
    }
    assert on_disk == referenced


def test_applications_are_valid_orm_data() -> None:
    columns = set(Application.__table__.columns.keys())
    for record in load_pool():
        app = ApplicationInput(**record["application"])  # validates types/bounds
        unknown = set(record["application"]) - columns
        assert not unknown, f"{record['id']}: unknown application fields {unknown}"
        assert app.brand_name


def test_annotation_blocks_match_use_cases() -> None:
    for record in load_pool():
        for use_case, block in _ANNOTATION_FOR.items():
            if use_case in record["use_cases"]:
                assert block in record, f"{record['id']} missing {block}"
        # Reviewer decisions only ride on demo (base_seed) rows.
        if "decision" in record:
            assert BASE_SEED in record["use_cases"], f"{record['id']} has a stray decision"


def test_seed_reads_no_data_outside_the_pool() -> None:
    """The old seed-private manifest copies are gone; the pool is the sole source."""
    data = resources.files("app.seed") / "data"
    assert not data.is_dir(), "app/seed/data must not exist — seed reads only app.pool"


def test_corpus_view_stays_in_sync_with_upstream_author() -> None:
    """The corpus_golden records must mirror tests/corpus (its authoring source).

    The synthetic corpus is authored by ``tests/corpus/cases.py`` (which renders
    the images and writes ``tests/corpus/manifest.json``); the pool carries a
    migrated copy. This guards the two against drift — regenerate the pool after
    editing the corpus.
    """
    upstream = json.loads((Path(__file__).parent / "corpus" / "manifest.json").read_text())["cases"]
    pooled = {r["id"]: r for r in records_for(CORPUS_GOLDEN)}
    assert len(pooled) == len(upstream)
    for case in upstream:
        record = pooled[f"corpus_{case['id']}"]
        assert record["application"] == case["application"]
        assert record["images"] == [os.path.basename(case["image"])]
        assert record["corpus_golden"] == {
            "title": case["title"],
            "description": case["description"],
            "label": case["label"],
            "golden": case["golden"],
        }


@pytest.mark.parametrize("use_case", list(_USE_CASE_COUNTS))
def test_use_case_membership_is_non_empty(use_case: str) -> None:
    assert records_for(use_case), f"no records tagged {use_case}"
