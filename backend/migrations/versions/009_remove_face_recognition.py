"""Remove face recognition tables, columns, FACE enum value, and pgvector extension

Revision ID: 009_remove_face_recognition
Revises: 008_offline_sync
Create Date: 2026-11-25 21:40:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "009_remove_face_recognition"
down_revision: Union[str, None] = "008_offline_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS face_embeddings CASCADE")
    op.execute("ALTER TABLE participants DROP COLUMN IF EXISTS embedding_status")
    op.execute("UPDATE attendance SET method = 'MANUAL' WHERE method::text = 'FACE'")
    op.execute("CREATE TYPE attendance_method_new AS ENUM ('QR', 'MANUAL')")
    op.execute(
        "ALTER TABLE attendance ALTER COLUMN method TYPE attendance_method_new "
        "USING method::text::attendance_method_new"
    )
    op.execute("DROP TYPE attendance_method")
    op.execute("ALTER TYPE attendance_method_new RENAME TO attendance_method")
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE")


def downgrade() -> None:
    pass
