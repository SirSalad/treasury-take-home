"""Parse a CSV batch manifest into validated per-row expected COLA fields.

A manifest is a CSV with one row per label application: an ``image_filename``
column naming the label image in the upload, plus the expected COLA fields from
:class:`app.api.schemas.ApplicationInput` (``brand_name`` required; the rest
optional, verified only when supplied). Unrecognised columns are ignored, so an
importer's existing export can carry extra bookkeeping columns untouched.

Parsing is intentionally lenient at the *row* level — a bad value is recorded as
a per-row error (see :class:`ParsedRow`) rather than aborting the whole upload —
but strict at the *structure* level: a manifest with no header, no data rows, or
missing the required columns raises :class:`ManifestError` (a 4xx for the caller)
because no per-row recovery is possible.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.api.schemas import ApplicationInput

# Column naming the label image for a row; paired against the uploaded image set.
IMAGE_FILENAME_COLUMN = "image_filename"

# Expected-application columns recognised in the manifest (everything ApplicationInput
# accepts). Any other column is ignored.
_APPLICATION_FIELDS = frozenset(ApplicationInput.model_fields)


class ManifestError(ValueError):
    """The manifest itself is malformed (no per-row recovery is possible)."""


@dataclass
class ParsedRow:
    """One parsed manifest row.

    ``application`` is the validated expected COLA fields (``None`` when the row's
    field values failed validation); ``image_filename`` the referenced image
    (``None``/empty when the column was blank). ``errors`` is empty for a row that
    is structurally usable on its own — :func:`app.batch.ingest.ingest_batch`
    adds pairing errors (missing/duplicate image) on top during ingestion.
    """

    row_number: int
    image_filename: str | None
    application: ApplicationInput | None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the row parsed cleanly and names an image."""
        return not self.errors and self.application is not None and bool(self.image_filename)


def parse_manifest(content: str | bytes) -> list[ParsedRow]:
    """Parse manifest ``content`` into one :class:`ParsedRow` per data row.

    Raises :class:`ManifestError` for structural problems (empty file, missing
    required columns, header-only). Per-row field errors are attached to the
    returned rows, not raised.
    """
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ManifestError("Manifest is empty (no header row).")
    # Normalise header whitespace so " brand_name " maps like "brand_name".
    headers = [h.strip() for h in reader.fieldnames]
    reader.fieldnames = headers

    missing_columns = [c for c in (IMAGE_FILENAME_COLUMN, "brand_name") if c not in headers]
    if missing_columns:
        raise ManifestError(
            "Manifest is missing required column(s): " + ", ".join(missing_columns) + "."
        )

    rows = [_parse_row(i, raw) for i, raw in enumerate(reader, start=1)]
    if not rows:
        raise ManifestError("Manifest has a header but no data rows.")
    return rows


def _parse_row(row_number: int, raw: dict[str | None, object]) -> ParsedRow:
    """Validate one raw CSV row into a :class:`ParsedRow`."""
    # Drop the catch-all None key (values beyond the header) and trim whitespace.
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in raw.items()
        if key is not None
    }

    raw_filename = cleaned.get(IMAGE_FILENAME_COLUMN)
    image_filename = raw_filename if isinstance(raw_filename, str) and raw_filename else None
    errors: list[str] = []
    if not image_filename:
        errors.append(f"Missing '{IMAGE_FILENAME_COLUMN}'.")

    # Feed only recognised, non-blank fields to ApplicationInput; blanks fall back
    # to the schema's defaults (e.g. source/product_type) or stay unset (None).
    app_values = {
        key: value
        for key, value in cleaned.items()
        if key in _APPLICATION_FIELDS and value not in (None, "")
    }
    application: ApplicationInput | None = None
    try:
        application = ApplicationInput(**app_values)
    except ValidationError as exc:
        for err in exc.errors():
            location = ".".join(str(part) for part in err["loc"]) or "row"
            errors.append(f"{location}: {err['msg']}")

    return ParsedRow(
        row_number=row_number,
        image_filename=image_filename,
        application=application,
        errors=errors,
    )
