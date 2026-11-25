"""Add offline sync columns to attendance table

Revision ID: 008_offline_sync
Revises: 007_cloudflare_r2_storage
Create Date: 2026-11-25 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008_offline_sync"
down_revision: Union[str, None] = "007_cloudflare_r2_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE attendance
            ADD COLUMN IF NOT EXISTS local_uuid UUID,
            ADD COLUMN IF NOT EXISTS sync_source VARCHAR(20) DEFAULT 'cloud',
            ADD COLUMN IF NOT EXISTS synced_at TIMESTAMPTZ
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_local_uuid
            ON attendance (local_uuid)
            WHERE local_uuid IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_attendance_local_uuid")
    op.execute("""
        ALTER TABLE attendance
            DROP COLUMN IF EXISTS local_uuid,
            DROP COLUMN IF EXISTS sync_source,
            DROP COLUMN IF EXISTS synced_at
    """)
