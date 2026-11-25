"""Event-scoped users and coupon code system

Revision ID: 003_event_scoped_users_and_coupons
Revises: 002_multi_event_payment
Create Date: 2026-11-23 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_event_users_coupons"
down_revision: Union[str, None] = "002_multi_event_payment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Create audit_log table if not exists (for audit helper)
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            actor_id INTEGER,
            actor_role VARCHAR(32),
            action VARCHAR(64) NOT NULL,
            entity VARCHAR(64),
            entity_id VARCHAR(64),
            before_json TEXT,
            after_json TEXT,
            ip VARCHAR(64),
            user_agent VARCHAR(255),
            request_id VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_actor_id ON audit_log (actor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log (action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_entity ON audit_log (entity)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_request_id ON audit_log (request_id)")

    # 1. Add event_id and password_changed_at to users
    op.add_column("users", sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_users_event_id", "users", ["event_id"])
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ")

    # 2. Add coupon_code, source, and status on participants
    op.execute("ALTER TABLE participants ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50)")
    op.execute("ALTER TABLE participants ADD COLUMN IF NOT EXISTS source VARCHAR(9) NOT NULL DEFAULT 'ONLINE'")
    op.execute("ALTER TABLE participants ADD COLUMN IF NOT EXISTS status VARCHAR(15) NOT NULL DEFAULT 'CONFIRMED'")
    op.execute("ALTER TABLE participants ALTER COLUMN source SET DEFAULT 'ONLINE'")
    op.execute("ALTER TABLE participants ALTER COLUMN status SET DEFAULT 'CONFIRMED'")

    # 3. Create coupons table
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False, index=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("max_uses", sa.Integer, nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "code", name="uq_event_coupon_code"),
    )

    # 4. Associate existing admin/volunteer with OAIC (event_id = 1)
    op.execute("UPDATE users SET event_id = 1 WHERE event_id IS NULL")

    # 5. Insert dedicated OAIC admin user (oaic_admin@geekai.in / oaic123)
    op.execute("""
        INSERT INTO users (email, password_hash, name, role, is_active, event_id, created_at)
        VALUES (
            'oaic_admin@geekai.in',
            '$2b$12$dFGNfJ6zH/WEo8AdrGlgYen5i0FqgRylTUMb/S4zxNX56hzQIXTxu',
            'OAIC Conference Admin',
            'ADMIN',
            true,
            1,
            NOW()
        )
        ON CONFLICT (email) DO UPDATE SET event_id = 1
    """)

    # 6. Insert Event 2: National Robotics Summit (NRS)
    op.execute("""
        INSERT INTO events (id, name, slug, description, tagline, logo_url, registration_fee, is_active, event_date, venue, website, created_at)
        VALUES (
            2,
            'National Robotics Summit (NRS)',
            'nrs',
            'National Robotics Summit is India premier conference on robotics, autonomy, embedded systems, and human-machine interaction.',
            'Innovations in Autonomous Robotics',
            'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=200&auto=format&fit=crop&q=60',
            50000,
            true,
            '2026-03-20 09:00:00+05:30',
            'IIT Bhubaneswar, Odisha',
            'https://robotics-summit.geekai.in',
            NOW()
        )
        ON CONFLICT (id) DO NOTHING
    """)

    # 7. Insert NRS Admin user (nrs_admin@geekai.in / nrs123)
    op.execute("""
        INSERT INTO users (email, password_hash, name, role, is_active, event_id, created_at)
        VALUES (
            'nrs_admin@geekai.in',
            '$2b$12$7GuYx27OuW.u4SgOoh21GOnjWOObF7zCGh0e/I9lDXClHDY.zP/EC',
            'NRS Summit Admin',
            'ADMIN',
            true,
            2,
            NOW()
        )
        ON CONFLICT (email) DO UPDATE SET event_id = 2
    """)

    # 8. Insert sample sessions for Event 2 (NRS)
    op.execute("""
        INSERT INTO sessions (name, description, start_time, end_time, location, event_id, created_at)
        VALUES
        (
            'Keynote: Autonomous Drones in Search & Rescue',
            'Exploring vision-based navigation and obstacle avoidance in GPS-denied environments.',
            '2026-03-20 10:00:00+05:30',
            '2026-03-20 11:30:00+05:30',
            'Auditorium A, IIT Bhubaneswar',
            2,
            NOW()
        ),
        (
            'Hands-on Workshop: ROS2 on Embedded Hardware',
            'Building distributed robot controllers with ROS2 Humble on Raspberry Pi & ESP32.',
            '2026-03-20 14:00:00+05:30',
            '2026-03-20 16:30:00+05:30',
            'Robotics Lab 2',
            2,
            NOW()
        )
    """)

    # 9. Insert sample coupons for OAIC and NRS
    op.execute("""
        INSERT INTO coupons (code, event_id, description, max_uses, used_count, is_active, created_at)
        VALUES
        ('OAICFREE', 1, 'OAIC Free Registration Pass', 10, 0, true, NOW()),
        ('VIP2026', 1, 'OAIC One-Time VIP Pass', 1, 0, true, NOW()),
        ('NRSFREE', 2, 'NRS Free Registration Pass', 10, 0, true, NOW()),
        ('ROBOT2026', 2, 'NRS One-Time Speaker Pass', 1, 0, true, NOW())
        ON CONFLICT ON CONSTRAINT uq_event_coupon_code DO NOTHING
    """)

    # 10. Sync events_id_seq after explicit id=1 and id=2 inserts
    op.execute("SELECT setval(pg_get_serial_sequence('events', 'id'), COALESCE((SELECT MAX(id) FROM events), 1))")


def downgrade() -> None:
    op.drop_table("coupons")
    op.drop_column("participants", "coupon_code")
    op.drop_index("ix_users_event_id", table_name="users")
    op.drop_column("users", "event_id")
