"""Typed schema for the label test corpus.

The corpus is a small set of labelled examples that drive the extractor,
verification, and performance tests. Each :class:`CorpusCase` bundles three
things:

* ``application`` — the *expected* COLA (TTB 5100.31 / 1513-0020) data an agent
  files. Shapes match :class:`app.models.application.Application`.
* ``label`` — what is physically *printed* on the rendered label image. This is
  the ground truth the OCR extractor must recover; it deliberately differs from
  ``application`` in the mismatch/altered cases.
* ``golden`` — the verdict the verification engine is expected to produce, both
  overall and per field, plus the special government-warning result.

The committed artifact is ``manifest.json``; this module defines the in-memory
shapes plus (de)serialisation so both the generator and the tests share one
source of truth. Enums mirror the project's ``StrEnum`` style.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).parent
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
IMAGES_DIR = CORPUS_DIR / "images"


class FieldVerdict(enum.StrEnum):
    """Per-field outcome of comparing the label against the application.

    Three states per the verification-engine design: a clean ``MATCH``, a
    ``SOFT_WARNING`` for human-equivalent differences (Dave's "STONE'S THROW"
    vs "Stone's Throw" case nuance), and a hard ``MISMATCH``. ``NOT_CHECKED``
    marks fields absent from the application (nothing to verify against).
    """

    MATCH = "match"
    SOFT_WARNING = "soft_warning"
    MISMATCH = "mismatch"
    NOT_CHECKED = "not_checked"


class WarningVerdict(enum.StrEnum):
    """Outcome of the mandatory Government Health Warning check.

    The warning gets a dedicated exact-match path: it must be present, contain
    the required statement verbatim, and render ``GOVERNMENT WARNING:`` in all
    caps. ``ALTERED`` covers wording/casing tampering (Jenny's title-case
    catch); ``MISSING`` covers an absent warning entirely.
    """

    COMPLIANT = "compliant"
    ALTERED = "altered"
    MISSING = "missing"


class OverallVerdict(enum.StrEnum):
    """Roll-up verdict surfaced to the agent for the whole label."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


# The exact mandatory Government Health Warning text (27 CFR 16.21). The
# `GOVERNMENT WARNING:` prefix must appear in all caps and bold on the label.
GOVERNMENT_WARNING_TEXT = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)


@dataclass
class Golden:
    """Expected verification verdict for a case."""

    overall: OverallVerdict
    # Logical field key -> expected per-field verdict. Keys are the application
    # attributes the engine compares: brand_name, class_type, alcohol_content,
    # net_contents, name_and_address, etc.
    fields: dict[str, FieldVerdict]
    government_warning: WarningVerdict
    # Human-readable note on *why* this is the golden verdict.
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "fields": {k: v.value for k, v in self.fields.items()},
            "government_warning": self.government_warning.value,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Golden:
        return cls(
            overall=OverallVerdict(data["overall"]),
            fields={k: FieldVerdict(v) for k, v in data["fields"].items()},
            government_warning=WarningVerdict(data["government_warning"]),
            rationale=data.get("rationale", ""),
        )


@dataclass
class CorpusCase:
    """One labelled example: expected application, printed label, golden verdict."""

    id: str
    title: str
    description: str
    # Relative path (from the corpus dir) to the rendered label image.
    image: str
    # Expected COLA fields — keys match Application model columns.
    application: dict[str, Any]
    # What is physically printed on the label image (extractor ground truth).
    label: dict[str, Any]
    golden: Golden

    def image_path(self) -> Path:
        return CORPUS_DIR / self.image

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["golden"] = self.golden.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CorpusCase:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            image=data["image"],
            application=data["application"],
            label=data["label"],
            golden=Golden.from_dict(data["golden"]),
        )


@dataclass
class Manifest:
    """The full corpus: a versioned list of cases."""

    version: int
    cases: list[CorpusCase] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "count": len(self.cases),
            "cases": [c.to_dict() for c in self.cases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        return cls(
            version=data["version"],
            cases=[CorpusCase.from_dict(c) for c in data["cases"]],
        )

    def to_json(self) -> str:
        """Pretty, stable JSON (sorted-free but deterministic key order)."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"


def load_manifest(path: Path = MANIFEST_PATH) -> Manifest:
    """Load and parse the committed corpus manifest."""
    return Manifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
