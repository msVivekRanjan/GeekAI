"""Convert participants.category from fixed enum to VARCHAR(100) for dynamic categories

Revision ID: 011_dynamic_participant_category
Revises: 010_add_attendance_event_id
Create Date: 2026-11-27 02:08:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "011_dynamic_participant_category"
down_revision: Union[str, None] = "010_add_attendance_event_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE participants ALTER COLUMN category DROP DEFAULT")
    op.execute("ALTER TABLE participants ALTER COLUMN category TYPE VARCHAR(100) USING category::text")
    op.execute("ALTER TABLE participants ALTER COLUMN category SET DEFAULT 'OTHER'")
    op.execute("DROP TYPE IF EXISTS participant_category")


def downgrade() -> None:
    pass
