"""FastAPI dependency injection: database session & current user.

Stage S1 extends the original `get_current_user`/`get_current_admin` with
`get_current_staff`, `get_hub_or_station` and `require_event_scope`
exactly as `Backend-Planning.md` §4.2 defines. JWT claims carry `role`,
`event_ids` and optional `station_id`/`hub_id`; an event mismatch is
**403**, never a silent fallback.
"""

from __future__ import annotations

from typing import AsyncGenerator, Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import decode_access_token, token_claims
from app.models.models import User, UserRole

# ---------------------------------------------------------------------------
# Database engine & session factory (initialised once at import time)
# ---------------------------------------------------------------------------

_engine_kwargs: dict = {
    "echo": False,
    "future": True,
    "connect_args": settings.async_connect_args,
}
if settings.is_serverless_db:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    _engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 300

engine = create_async_engine(settings.async_database_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the bearer token to a User, attaching verified JWT claims."""
    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise _credentials_exception
    except JWTError:
        raise _credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _credentials_exception

    # Attach claims so downstream dependencies can inspect role/event scope.
    user._token_claims = payload  # type: ignore[attr-defined]
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the bearer token to an active user (any role).

    Kept for backward compatibility with existing callers. Prefer
    `get_current_staff`, `get_current_admin` or `get_hub_or_station`
    for new code.
    """
    return await _get_current_user(token, db)


def _claims(user: User) -> dict:
    return getattr(user, "_token_claims", {}) or {}


async def get_current_staff(user: User = Depends(get_current_user)) -> User:
    """Return the user if they are staff (admin or volunteer), else 403."""
    role = _claims(user).get("role", user.role.value if hasattr(user.role, "value") else user.role)
    if role not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, UserRole.VOLUNTEER.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff privileges required",
        )
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Return the user if they are an admin (or super admin), else 403."""
    role = _claims(user).get("role", user.role.value if hasattr(user.role, "value") else user.role)
    if role not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


async def get_current_super_admin(user: User = Depends(get_current_user)) -> User:
    """Return the user if they are a super admin, else 403."""
    role = _claims(user).get("role", user.role.value if hasattr(user.role, "value") else user.role)
    if role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required",
        )
    return user


async def get_hub_or_station(user: User = Depends(get_current_user)) -> User:
    """Return the user if they are a hub or station principal, else 403.

    Hub/station tokens carry `station_id` or `hub_id` in their JWT claims.
    """
    claims = _claims(user)
    if "station_id" not in claims and "hub_id" not in claims:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hub or station privileges required",
        )
    return user


def require_event_scope(event_id: str) -> Callable[[User], User]:
    """Return a dependency that requires `event_id` in the JWT `event_ids`.

    A token for the wrong event — or without `event_ids` — is **403**,
    never a silent fallback.
    """

    async def dependency(user: User = Depends(get_current_staff)) -> User:
        claims = _claims(user)
        role = claims.get("role", user.role.value if hasattr(user.role, "value") else user.role)
        if role == UserRole.SUPER_ADMIN.value:
            return user
        event_ids: List[str] = list(claims.get("event_ids", []))
        if event_id not in event_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Event scope '{event_id}' not authorised for this principal",
            )
        return user

    return dependency


def get_request_id(request: Request) -> str:
    """Return the request id assigned by the request-id middleware."""
    return getattr(request.state, "request_id", "")
