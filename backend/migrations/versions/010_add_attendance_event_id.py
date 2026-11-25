"""Safely add attendance.event_id with validated backfill, FK, index, and NOT NULL

Revision ID: 010_add_attendance_event_id
Revises: 009_remove_face_recognition
Create Date: 2026-11-26 01:35:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "010_add_attendance_event_id"
down_revision: Union[str, None] = "009_remove_face_recognition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_id INTEGER")

    op.execute("""
        UPDATE attendance a
        SET event_id = p.event_id
        FROM participants p
        WHERE a.participant_id = p.id
          AND a.event_id IS NULL
          AND p.event_id IS NOT NULL
          AND (
              a.session_id IS NULL
              OR EXISTS (
                  SELECT 1
                  FROM sessions s
                  WHERE s.id = a.session_id
                    AND (s.event_id IS NULL OR s.event_id = p.event_id)
              )
          )
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM attendance WHERE event_id IS NULL) THEN
                RAISE EXCEPTION 'Cannot set attendance.event_id NOT NULL: % unbackfilled/inconsistent rows remain',
                    (SELECT count(*) FROM attendance WHERE event_id IS NULL);
            END IF;
        END $$;
    """)

    op.execute("ALTER TABLE attendance ALTER COLUMN event_id SET NOT NULL")
    op.execute("""
        ALTER TABLE attendance
            ADD CONSTRAINT attendance_event_id_fkey
            FOREIGN KEY (event_id) REFERENCES events(id)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_attendance_event_id ON attendance (event_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_attendance_event_id")
    op.execute("ALTER TABLE attendance DROP CONSTRAINT IF EXISTS attendance_event_id_fkey")
    op.execute("ALTER TABLE attendance DROP COLUMN IF EXISTS event_id")
