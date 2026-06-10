"""Result schemas for batch ingestion.

:class:`BatchIngestResult` is the contract the batch-create API returns so an
agent can fix a bad manifest before processing: it pairs the persisted batch id
with a full account of what went wrong — per-row errors, manifest rows whose
image was not uploaded (``missing_files``), and uploaded images no row referenced
(``extra_files``).
"""

from __future__ import annotations

from pydantic import BaseModel


class RowError(BaseModel):
    """One manifest row that could not be paired into the batch.

    ``row_number`` is 1-based over the manifest's *data* rows (the header is not
    counted). ``messages`` collects every reason the row was rejected — bad/
    missing field values, a missing image file, or an ambiguous filename — so the
    agent can fix them all in one pass rather than one error at a time.
    """

    row_number: int
    image_filename: str | None
    messages: list[str]


class BatchIngestResult(BaseModel):
    """Outcome of ingesting a manifest + image set.

    ``batch_id`` is the persisted :class:`app.models.batch.Batch` when at least
    one row paired successfully, else ``None`` (nothing was persisted). ``paired``
    is the number of items written to the batch; ``total_rows`` the number of
    data rows in the manifest.
    """

    batch_id: int | None
    total_rows: int
    paired: int
    row_errors: list[RowError]
    # Filenames referenced by an otherwise-valid row but absent from the upload.
    missing_files: list[str]
    # Uploaded images that no manifest row referenced.
    extra_files: list[str]

    @property
    def ok(self) -> bool:
        """True when every row paired cleanly with no leftover images."""
        return not self.row_errors and not self.extra_files and self.paired == self.total_rows
