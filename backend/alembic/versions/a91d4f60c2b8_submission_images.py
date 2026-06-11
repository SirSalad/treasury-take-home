"""submission images

A COLA filing comprises several label images (front/back/neck), and the
mandatory content is split across them — the Government Warning usually sits
on the back label. ``submission_images`` stores the ordered image set per
submission; existing single-image rows are backfilled as one-image sets so
every submission's images can be read from one place. ``submissions.image_ref``
remains as a denormalised mirror of the first image.

Revision ID: a91d4f60c2b8
Revises: c3f82e11d4b7
Create Date: 2026-06-11 19:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a91d4f60c2b8"
down_revision: Union[str, Sequence[str], None] = "c3f82e11d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "submission_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=True),
        sa.Column("image_ref", sa.String(length=512), nullable=False),
        sa.Column("image_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", "position", name="uq_submission_image_position"),
    )
    op.create_index(
        op.f("ix_submission_images_submission_id"),
        "submission_images",
        ["submission_id"],
        unique=False,
    )

    # Backfill: every existing submission becomes a one-image set.
    op.execute(
        sa.text(
            "INSERT INTO submission_images "
            "(submission_id, position, image_ref, image_filename, content_type) "
            "SELECT id, 0, image_ref, image_filename, content_type "
            "FROM submissions WHERE image_ref IS NOT NULL"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_submission_images_submission_id"), table_name="submission_images")
    op.drop_table("submission_images")
