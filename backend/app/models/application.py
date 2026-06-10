"""Application model: the *expected* label data from TTB form 5100.31.

TTB Form 5100.31 (OMB Control No. 1513-0020), "Application for and
Certification/Exemption of Label/Bottle Approval" (a.k.a. COLA), is what a
producer/importer files. For this prototype it represents the ground truth an
agent verifies the physical label artwork against: brand name, class/type,
alcohol content, net contents, and so on.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ProductSource, ProductType
from app.models.types import TimestampMixin

if TYPE_CHECKING:
    from app.models.submission import Submission


class Application(TimestampMixin, Base):
    """Expected label fields filed on a TTB COLA application (1513-0020)."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Identification ---
    # TTB Serial Number (block 5 on the form: e.g. "24-001").
    serial_number: Mapped[str | None] = mapped_column(String(32), index=True)
    # Plant Registry / Basic Permit / Brewer's Number.
    plant_registry_number: Mapped[str | None] = mapped_column(String(64))

    source: Mapped[ProductSource] = mapped_column(
        SAEnum(ProductSource, native_enum=False, length=16), nullable=False
    )
    product_type: Mapped[ProductType] = mapped_column(
        SAEnum(ProductType, native_enum=False, length=24), nullable=False
    )

    # --- Label content the agent verifies ---
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    fanciful_name: Mapped[str | None] = mapped_column(String(255))
    # Class/type designation, e.g. "Kentucky Straight Bourbon Whiskey".
    class_type: Mapped[str | None] = mapped_column(String(255))

    # Alcohol content: keep both the parsed percentage and the raw label text,
    # since labels phrase it many ways ("45% Alc./Vol. (90 Proof)").
    alcohol_content_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    alcohol_content_text: Mapped[str | None] = mapped_column(String(64))

    net_contents: Mapped[str | None] = mapped_column(String(64))

    # Name and address of the bottler/producer/importer.
    name_and_address: Mapped[str | None] = mapped_column(Text)
    # Required on imports; null for domestic product.
    country_of_origin: Mapped[str | None] = mapped_column(String(128))

    # --- Wine-specific optional fields ---
    appellation: Mapped[str | None] = mapped_column(String(128))
    vintage: Mapped[str | None] = mapped_column(String(8))

    formula: Mapped[str | None] = mapped_column(String(128))

    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Application id={self.id} brand={self.brand_name!r}>"
