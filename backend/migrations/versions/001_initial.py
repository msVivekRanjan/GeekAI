"""Initial schema — users, participants, sessions, attendance

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    user_role = sa.Enum("ADMIN", "VOLUNTEER", name="user_role")
    participant_category = sa.Enum(
        "STUDENT", "RESEARCHER", "PROFESSIONAL", "SPEAKER", "OTHER",
        name="participant_category",
    )
    attendance_method = sa.Enum("QR", "MANUAL", name="attendance_method")

    # -- users ----------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="VOLUNTEER"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- participants ---------------------------------------------------------
    op.create_table(
        "participants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), unique=True, nullable=False, index=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("institution", sa.String(255), nullable=True),
        sa.Column("category", participant_category, nullable=False, server_default="OTHER"),
        sa.Column("photo_url", sa.String(512), nullable=True),
        sa.Column("qr_code_url", sa.String(512), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- sessions -------------------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # -- attendance -----------------------------------------------------------
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "participant_id",
            sa.Integer,
            sa.ForeignKey("participants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("method", attendance_method, nullable=False),
        sa.Column("marked_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id", "session_id", name="uq_participant_session"),
    )

    # Partial unique index for event-level attendance (session_id IS NULL)
    op.execute(
        "CREATE UNIQUE INDEX unique_event_attendance ON attendance(participant_id) WHERE session_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS unique_event_attendance")
    op.drop_table("attendance")
    op.drop_table("sessions")
    op.drop_table("participants")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS attendance_method")
    op.execute("DROP TYPE IF EXISTS participant_category")
    op.execute("DROP TYPE IF EXISTS user_role")
