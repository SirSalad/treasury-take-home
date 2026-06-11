"""CLI entry: ``python -m app.seed`` — seed demo data into an empty database."""

from app.config import get_settings
from app.db import _session_factory
from app.ocr import get_ocr_service
from app.seed import seed_demo


def main() -> None:
    settings = get_settings()
    with _session_factory()() as db:
        created = seed_demo(db, get_ocr_service(), upload_dir=settings.upload_dir)
    if created:
        print(f"[seed] Seeded {created} demo submissions.")
    else:
        print("[seed] Database already has submissions; nothing seeded.")


if __name__ == "__main__":
    main()
