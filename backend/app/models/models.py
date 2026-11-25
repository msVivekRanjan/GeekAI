"""SQLAlchemy ORM models for GeekAI."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    VOLUNTEER = "VOLUNTEER"


class ParticipantCategory(str, enum.Enum):
    STUDENT = "STUDENT"
    RESEARCHER = "RESEARCHER"
    PROFESSIONAL = "PROFESSIONAL"
    SPEAKER = "SPEAKER"
    OTHER = "OTHER"


class AttendanceMethod(str, enum.Enum):
    QR = "QR"
    MANUAL = "MANUAL"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, name="user_role"), nullable=False, default=UserRole.VOLUNTEER)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    attendances_marked = relationship(
        "Attendance",
        back_populates="marked_by_user",
        foreign_keys="Attendance.marked_by",
    )
    event = relationship("Event", back_populates="users", foreign_keys=[event_id])


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(320), nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    institution = Column(String(255), nullable=True)
    category = Column(
        Enum(ParticipantCategory, name="participant_category"),
        nullable=False,
        default=ParticipantCategory.OTHER,
    )
    photo_url = Column(String(512), nullable=True)
    qr_code_url = Column(String(512), nullable=True)
    photo_object_key = Column(String(512), nullable=True)
    qr_object_key = Column(String(512), nullable=True)
    registered_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)
    source = Column(String(9), nullable=False, default="ONLINE")
    status = Column(String(15), nullable=False, default="CONFIRMED")
    payment_order_id = Column(String(255), nullable=True)
    payment_status = Column(String(50), nullable=True, default="PENDING")  # PENDING, SUCCESS, FAILED
    coupon_code = Column(String(50), nullable=True)

    # Custom form responses (JSONB for dynamic form fields)
    custom_responses = Column(JSONB, nullable=True)

    # Relationships
    attendances = relationship("Attendance", back_populates="participant", cascade="all, delete-orphan")
    event = relationship("Event", back_populates="participants")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    location = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)

    # Relationships
    attendances = relationship("Attendance", back_populates="session", cascade="all, delete-orphan")
    event = relationship("Event", back_populates="sessions")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("participant_id", "session_id", name="uq_participant_session"),
        Index(
            "unique_event_attendance",
            "participant_id",
            unique=True,
            postgresql_where="session_id IS NULL",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    participant_id = Column(Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    method = Column(Enum(AttendanceMethod, name="attendance_method"), nullable=False)
    marked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    marked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, default=1, index=True)
    # Offline sync columns
    local_uuid = Column(PG_UUID(as_uuid=True), nullable=True, unique=False, index=True)
    sync_source = Column(String(20), nullable=False, default="cloud")
    synced_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    participant = relationship("Participant", back_populates="attendances")
    session = relationship("Session", back_populates="attendances")
    marked_by_user = relationship("User", back_populates="attendances_marked")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    tagline = Column(String(255), nullable=True)
    logo_url = Column(String(512), nullable=True)
    banner_url = Column(String(512), nullable=True)
    registration_fee = Column(Integer, nullable=False, default=0)  # in paise/smallest unit
    is_active = Column(Boolean, default=True, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    registration_form_schema = Column(JSONB, nullable=True)
    registration_form_version = Column(Integer, nullable=False, default=1)
    form_image_url = Column(String(512), nullable=True)
    cashfree_enabled = Column(Boolean, default=False, nullable=False)
    cashfree_app_id = Column(String(255), nullable=True)
    cashfree_secret_key = Column(String(512), nullable=True)
    cashfree_env = Column(String(20), default="sandbox", nullable=False)
    r2_enabled = Column(Boolean, default=False, nullable=False)
    r2_account_id = Column(String(255), nullable=True)
    r2_access_key_id = Column(String(255), nullable=True)
    r2_secret_access_key = Column(String(512), nullable=True)
    r2_bucket_name = Column(String(255), nullable=True)
    r2_public_url = Column(String(512), nullable=True)
    guidelines = Column(JSONB, nullable=True)
    event_date = Column(DateTime(timezone=True), nullable=True)
    venue = Column(String(255), nullable=True)
    registration_deadline = Column(DateTime(timezone=True), nullable=True)
    website = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    participants = relationship("Participant", back_populates="event")
    sessions = relationship("Session", back_populates="event")
    users = relationship("User", back_populates="event", foreign_keys="User.event_id")
    coupons = relationship("Coupon", back_populates="event", cascade="all, delete-orphan")


class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        UniqueConstraint("event_id", "code", name="uq_event_coupon_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(255), nullable=True)
    max_uses = Column(Integer, nullable=False, default=1)
    used_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="coupons")


class StoredFile(Base):
    __tablename__ = "stored_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=True, index=True)
    category = Column(String(50), nullable=False)  # participant_photos | form_uploads | documents | qr_codes
    object_key = Column(String(512), unique=True, nullable=False, index=True)
    public_url = Column(String(1024), nullable=False)
    original_filename = Column(String(255), nullable=True)
    content_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    storage_provider = Column(String(20), nullable=False, default="local")  # r2 | local
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
