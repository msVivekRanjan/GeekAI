"""Super Admin role, event form builder, participant custom responses

Revision ID: 004_super_admin_form_builder
Revises: 003_event_users_coupons
Create Date: 2026-11-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004_super_admin_form_builder"
down_revision: Union[str, None] = "003_event_users_coupons"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add SUPER_ADMIN to user_role enum (requires autocommit outside transaction)
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'")

    # 2. Add form builder columns to events table
    op.execute("""
        ALTER TABLE events
            ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS registration_form_schema JSONB,
            ADD COLUMN IF NOT EXISTS registration_form_version INTEGER NOT NULL DEFAULT 1
    """)

    # 3. Add custom_responses to participants table
    op.execute("""
        ALTER TABLE participants
            ADD COLUMN IF NOT EXISTS custom_responses JSONB
    """)

    # 4. Update admin@geekai.in to SUPER_ADMIN role with no event_id
    op.execute("""
        UPDATE users
        SET role = 'SUPER_ADMIN', event_id = NULL
        WHERE email = 'admin@geekai.in'
    """)


def downgrade() -> None:
    # Revert admin@geekai.in back to ADMIN
    op.execute("""
        UPDATE users SET role = 'ADMIN', event_id = 1
        WHERE email = 'admin@geekai.in'
    """)

    # Drop added columns
    op.execute("""
        ALTER TABLE participants DROP COLUMN IF EXISTS custom_responses
    """)
    op.execute("""
        ALTER TABLE events
            DROP COLUMN IF EXISTS is_published,
            DROP COLUMN IF EXISTS registration_form_schema,
            DROP COLUMN IF EXISTS registration_form_version
    """)

    # Note: PostgreSQL doesn't support removing enum values easily.
    # SUPER_ADMIN enum value remains but is effectively unused after downgrade.
