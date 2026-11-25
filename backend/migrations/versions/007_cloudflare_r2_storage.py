"""Add Cloudflare R2 storage settings and stored_files metadata table

Revision ID: 007_cloudflare_r2_storage
Revises: 006_event_guidelines
Create Date: 2026-11-25 15:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007_cloudflare_r2_storage"
down_revision: Union[str, None] = "006_event_guidelines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE events
            ADD COLUMN IF NOT EXISTS r2_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS r2_account_id VARCHAR(255),
            ADD COLUMN IF NOT EXISTS r2_access_key_id VARCHAR(255),
            ADD COLUMN IF NOT EXISTS r2_secret_access_key VARCHAR(512),
            ADD COLUMN IF NOT EXISTS r2_bucket_name VARCHAR(255),
            ADD COLUMN IF NOT EXISTS r2_public_url VARCHAR(512);
    """)

    op.execute("""
        ALTER TABLE participants
            ADD COLUMN IF NOT EXISTS photo_object_key VARCHAR(512),
            ADD COLUMN IF NOT EXISTS qr_object_key VARCHAR(512);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS stored_files (
            id SERIAL PRIMARY KEY,
            event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            participant_id INTEGER REFERENCES participants(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            object_key VARCHAR(512) NOT NULL UNIQUE,
            public_url VARCHAR(1024) NOT NULL,
            original_filename VARCHAR(255),
            content_type VARCHAR(128),
            size_bytes INTEGER,
            storage_provider VARCHAR(20) NOT NULL DEFAULT 'local',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_stored_files_event_id ON stored_files (event_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stored_files_participant_id ON stored_files (participant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stored_files_object_key ON stored_files (object_key)")


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS stored_files;
        ALTER TABLE participants
            DROP COLUMN IF EXISTS photo_object_key,
            DROP COLUMN IF EXISTS qr_object_key;
        ALTER TABLE events
            DROP COLUMN IF EXISTS r2_enabled,
            DROP COLUMN IF EXISTS r2_account_id,
            DROP COLUMN IF EXISTS r2_access_key_id,
            DROP COLUMN IF EXISTS r2_secret_access_key,
            DROP COLUMN IF EXISTS r2_bucket_name,
            DROP COLUMN IF EXISTS r2_public_url;
    """)
