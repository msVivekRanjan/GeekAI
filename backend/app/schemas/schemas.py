"""Pydantic request/response schemas for GeekAI API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.models import AttendanceMethod, UserRole


# ===== Auth =================================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    name: str
    # True when the principal must change their password before further work.
    # Additive field — the delivered frontend ignores unknown response keys.
    must_change_password: bool = False
    event_ids: List[str] = []
    event_id: Optional[int] = None
    event_name: Optional[str] = None
    event_slug: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)
    role: UserRole = UserRole.VOLUNTEER


class BootstrapRequest(BaseModel):
    """One-time first-admin bootstrap request.

    `token` is the bootstrap secret from the environment (BOOTSTRAP_TOKEN).
    Only accepted while the users table is empty.
    """
    token: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class BootstrapResponse(BaseModel):
    """Bootstrap result: the first admin user plus their login token."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    must_change_password: bool = True


class ChangePasswordRequest(BaseModel):
    """First-login password change for the bootstrap admin."""
    current_password: str
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    event_id: Optional[int] = None
    event_name: Optional[str] = None

    class Config:
        from_attributes = True


class VolunteerOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    attendance_count: int = 0
    event_id: Optional[int] = None
    event_name: Optional[str] = None

    class Config:
        from_attributes = True


class VolunteerCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)
    event_id: Optional[int] = None


# ===== Participants =========================================================

class ParticipantCreate(BaseModel):
    """Fields submitted as form data (photo comes as UploadFile)."""
    name: str = Field(min_length=1)
    email: EmailStr
    phone: Optional[str] = None
    institution: Optional[str] = None
    category: str = Field(default="OTHER", min_length=1, max_length=100)
    coupon_code: Optional[str] = None


class ParticipantOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    institution: Optional[str] = None
    category: str
    photo_url: Optional[str] = None
    qr_code_url: Optional[str] = None
    photo_object_key: Optional[str] = None
    qr_object_key: Optional[str] = None
    registered_at: datetime
    event_id: Optional[int] = None
    source: Optional[str] = "ONLINE"
    status: Optional[str] = "CONFIRMED"
    payment_status: Optional[str] = None
    coupon_code: Optional[str] = None
    custom_responses: Optional[dict] = None

    class Config:
        from_attributes = True


class ParticipantDetail(ParticipantOut):
    attendances: List[AttendanceOut] = []

    class Config:
        from_attributes = True


class ParticipantList(BaseModel):
    total: int
    items: List[ParticipantOut]


class ParticipantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    institution: Optional[str] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    payment_status: Optional[str] = None
    status: Optional[str] = None


# ===== Sessions =============================================================

class SessionCreate(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None


class SessionOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetail(SessionOut):
    attendance_count: int = 0


# ===== Attendance ===========================================================

class AttendanceCreate(BaseModel):
    participant_id: int
    session_id: Optional[int] = None
    method: AttendanceMethod = AttendanceMethod.MANUAL


class AttendanceOut(BaseModel):
    id: int
    participant_id: int
    session_id: Optional[int] = None
    method: AttendanceMethod
    marked_by: int
    marked_at: datetime
    participant_name: Optional[str] = None
    session_name: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceStats(BaseModel):
    total_participants: int
    total_checked_in: int
    total_sessions: int
    attendance_by_method: dict
    attendance_by_session: List[dict]


class QRValidateRequest(BaseModel):
    participant_id: int
    name: str


class QRValidateResponse(BaseModel):
    valid: bool
    participant: Optional[ParticipantOut] = None
    message: str


# ===== Admin / Dashboard ====================================================

class DashboardStats(BaseModel):
    total_participants: int
    total_sessions: int
    total_attendance_records: int
    event_checkins: int
    participants_by_category: dict
    recent_registrations: List[ParticipantOut]


# ===== Events ===============================================================

class EventOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    form_image_url: Optional[str] = None
    registration_fee: int = 0  # in paise
    is_active: bool = True
    is_published: bool = False
    cashfree_enabled: bool = False
    cashfree_env: str = "sandbox"
    r2_enabled: bool = False
    guidelines: Optional[List[str]] = None
    event_date: Optional[datetime] = None
    venue: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    website: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Form Builder ==========================================================

class FormFieldOption(BaseModel):
    """An option for select/radio/checkbox group fields."""
    label: str
    value: str


class FormFieldValidation(BaseModel):
    """Optional validation rules for a field."""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None


class FormField(BaseModel):
    """A single field in a dynamic registration form."""
    id: str  # client-generated UUID
    type: str  # text|email|phone|number|dropdown|radio|checkbox|date|textarea|file|photo|image
    label: str
    placeholder: Optional[str] = None
    required: bool = False
    options: Optional[List[FormFieldOption]] = None  # for dropdown/radio/checkbox
    validation: Optional[FormFieldValidation] = None
    order: int = 0
    help_text: Optional[str] = None
    mapping: Optional[str] = None  # name|email|phone|institution|category|photo|custom
    image_url: Optional[str] = None  # for image field type
    object_key: Optional[str] = None  # R2 / storage object key for image deletion/management


class FormSchema(BaseModel):
    """Full form schema stored as JSONB in Event.registration_form_schema."""
    fields: List[FormField] = []
    version: int = 1


class EventCreate(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    form_image_url: Optional[str] = None
    registration_fee: int = Field(default=0, ge=0)
    cashfree_enabled: bool = False
    cashfree_app_id: Optional[str] = None
    cashfree_secret_key: Optional[str] = None
    cashfree_env: str = "sandbox"
    r2_enabled: bool = False
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None
    r2_public_url: Optional[str] = None
    guidelines: Optional[List[str]] = None
    event_date: Optional[datetime] = None
    venue: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    website: Optional[str] = None


class EventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    form_image_url: Optional[str] = None
    registration_fee: Optional[int] = Field(default=None, ge=0)
    cashfree_enabled: Optional[bool] = None
    cashfree_app_id: Optional[str] = None
    cashfree_secret_key: Optional[str] = None
    cashfree_env: Optional[str] = None
    r2_enabled: Optional[bool] = None
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None
    r2_public_url: Optional[str] = None
    guidelines: Optional[List[str]] = None
    is_active: Optional[bool] = None
    event_date: Optional[datetime] = None
    venue: Optional[str] = None
    registration_deadline: Optional[datetime] = None
    website: Optional[str] = None


class SuperAdminEventOut(EventOut):
    registration_form_schema: Optional[dict] = None
    registration_form_version: int = 1
    participant_count: int = 0
    cashfree_app_id: Optional[str] = None
    has_cashfree_secret: bool = False
    r2_enabled: bool = False
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_bucket_name: Optional[str] = None
    r2_public_url: Optional[str] = None
    has_r2_secret: bool = False
    admin_id: Optional[int] = None
    admin_email: Optional[str] = None
    admin_name: Optional[str] = None

    class Config:
        from_attributes = True


class EventAdminOut(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    role: UserRole
    event_id: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventAdminUpsert(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = True


# ===== Payments =============================================================

class CreateOrderRequest(BaseModel):
    event_slug: str
    amount: int  # in paise (e.g., 30000 = ₹300)
    customer_name: str
    customer_email: EmailStr
    customer_phone: Optional[str] = None


class CreateOrderResponse(BaseModel):
    order_id: str
    payment_session_id: str
    order_status: str


class VerifyPaymentRequest(BaseModel):
    order_id: str


class VerifyPaymentResponse(BaseModel):
    order_id: str
    order_status: str
    paid: bool
    amount: int  # in paise


class ReconcilePaymentRequest(BaseModel):
    order_id: str
    email: Optional[EmailStr] = None


class ReconcilePaymentResponse(BaseModel):
    reconciled: bool
    message: str
    order_id: str
    paid: bool
    participant: Optional[ParticipantOut] = None


# ===== Coupons ===============================================================

class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    description: Optional[str] = None
    max_uses: int = Field(default=1, ge=1)
    is_active: bool = True
    event_id: Optional[int] = None


class CouponOut(BaseModel):
    id: int
    code: str
    event_id: int
    event_name: Optional[str] = None
    description: Optional[str] = None
    max_uses: int = 1
    used_count: int = 0
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class ValidateCouponRequest(BaseModel):
    code: str


class ValidateCouponResponse(BaseModel):
    valid: bool
    code: str
    message: str
    event_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Offline Sync
# ---------------------------------------------------------------------------

class OfflineAttendanceRecord(BaseModel):
    """A single attendance record submitted from the offline volunteer app."""
    local_uuid: UUID
    participant_id: int
    session_id: Optional[int] = None
    method: str  # QR | MANUAL
    marked_at: Optional[str] = None  # ISO timestamp
    event_id: int


class OfflineSyncBatch(BaseModel):
    """Batch of offline attendance records to sync."""
    records: List[OfflineAttendanceRecord]


class OfflineSyncResult(BaseModel):
    """Per-record result from an offline sync batch."""
    local_uuid: UUID
    status: str  # synced | already_synced | duplicate | error
    message: str = ""
    attendance_id: Optional[int] = None


class OfflineSyncResponse(BaseModel):
    """Response from the batch sync endpoint."""
    total: int
    synced: int
    skipped: int
    errors: int
    results: List[OfflineSyncResult]


# ---------------------------------------------------------------------------
# Resolve forward references
# ---------------------------------------------------------------------------
ParticipantDetail.model_rebuild()
BootstrapResponse.model_rebuild()
