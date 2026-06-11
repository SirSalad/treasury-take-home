"""submission review decision

Adds the reviewer-decision columns to submissions: the human judgment
(approve / request_changes / request_info) recorded on top of the automated
verdict, with an optional internal note and timestamp. Null decision means
the submission is still in the review queue.

Revision ID: b7c41d20a9e1
Revises: e159073954d6
Create Date: 2026-06-11 01:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b7c41d20a9e1"
down_revision: Union[str, Sequence[str], None] = "e159073954d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("submissions", sa.Column("decision", sa.String(length=32), nullable=True))
    op.add_column("submissions", sa.Column("decision_note", sa.Text(), nullable=True))
    op.add_column("submissions", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_submissions_decision"), "submissions", ["decision"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_submissions_decision"), table_name="submissions")
    op.drop_column("submissions", "decided_at")
    op.drop_column("submissions", "decision_note")
    op.drop_column("submissions", "decision")
