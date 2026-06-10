"""Batch ingestion: pair a CSV manifest with an uploaded image set.

Importers drop hundreds of label applications at once during peak season (per
the Compliance Division interviews). This package turns a *manifest + images*
upload into a validated :class:`app.models.batch.Batch` of ``PENDING``
submissions ready for the processing queue:

* :func:`app.batch.manifest.parse_manifest` parses the CSV into per-row expected
  COLA fields, collecting per-row validation errors instead of failing fast.
* :func:`app.batch.ingest.ingest_batch` pairs rows to image files by filename —
  reporting missing files, extra files, and ambiguous (duplicate) references —
  and persists the batch with one :class:`app.models.batch.BatchItem` per valid,
  paired row.
"""

from app.batch.ingest import ingest_batch
from app.batch.manifest import ManifestError, ParsedRow, parse_manifest
from app.batch.schemas import BatchIngestResult, RowError

__all__ = [
    "BatchIngestResult",
    "ManifestError",
    "ParsedRow",
    "RowError",
    "ingest_batch",
    "parse_manifest",
]
