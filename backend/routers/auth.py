import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.platform import Tenant, User
from app.core.security import (
    create_access_token,
    verify_password,
    check_login_rate_limit,
    record_login_failure,
    reset_login_failures,
    get_role_permissions,
)
from app.api.deps import get_current_user
from routers import ws_copilot
from config import settings

logger = logging.getLogger("voicedesk.routers.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    tenant_slug: str = Field(..., description="Target tenant slug, e.g. sai-smile")
    email: Optional[str] = Field(None, description="User email or phone")
    identifier: Optional[str] = Field(None, description="User email or phone identifier")
    password: str = Field(..., description="User password")

    @property
    def login_identity(self) -> str:
        return (self.email or self.identifier or "").strip()


class UserSummary(BaseModel):
    id: str
    tenant_id: str
    tenant_slug: str
    email: Optional[str]
    full_name: str
    role: str
    permissions: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Tenant-aware authentication endpoint.
    Verifies tenant identity, user credentials, enforces rate limits,
    and returns a short-lived cryptographically signed JWT access token.
    """
    identity = req.login_identity
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email or identifier is required",
        )

    redis_client = None
    try:
        redis_client = await ws_copilot.get_redis_client()
    except Exception:
        pass

    client_ip = request.client.host if request.client else "unknown"
    rate_identity = f"{client_ip}:{req.tenant_slug}:{identity}"

    # 1. Rate limiting check
    if redis_client:
        await check_login_rate_limit(redis_client, rate_identity)

    # 2. Resolve Tenant
    tenant_stmt = select(Tenant).where(Tenant.slug == req.tenant_slug.strip().lower(), Tenant.is_active.is_(True))
    tenant_res = await db.execute(tenant_stmt)
    tenant = tenant_res.scalar_one_or_none()

    if tenant is None:
        if redis_client:
            await record_login_failure(redis_client, rate_identity)
        logger.warning(f"Failed login attempt: Tenant '{req.tenant_slug}' not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant, user identifier, or password",
        )

    # 3. Resolve User inside Tenant
    user_stmt = select(User).where(
        User.tenant_id == tenant.id,
        (User.email == identity) | (User.phone == identity),
    )
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if user is None:
        if redis_client:
            await record_login_failure(redis_client, rate_identity)
        logger.warning(f"Failed login attempt: User '{identity}' not found for tenant '{tenant.slug}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant, user identifier, or password",
        )

    if not user.is_active:
        if redis_client:
            await record_login_failure(redis_client, rate_identity)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # 4. Verify Password
    if not user.hashed_password or not verify_password(req.password, user.hashed_password):
        if redis_client:
            await record_login_failure(redis_client, rate_identity)
        logger.warning(f"Failed login attempt: Invalid password for user '{identity}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant, user identifier, or password",
        )

    # 5. Reset failed rate limit counter on success
    if redis_client:
        await reset_login_failures(redis_client, rate_identity)

    # 6. Update last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # 7. Issue JWT Access Token
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(tenant.id),
        tenant_slug=tenant.slug,
        role=user.role,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserSummary(
            id=str(user.id),
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            permissions=get_role_permissions(user.role),
        ),
    )


@router.post("/logout")
async def logout():
    """Client logout confirmation endpoint."""
    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserSummary)
async def get_me(user_and_tenant = Depends(get_current_user)):
    """Returns currently authenticated user profile and permissions."""
    user, tenant = user_and_tenant
    return UserSummary(
        id=str(user.id),
        tenant_id=str(tenant.id),
        tenant_slug=tenant.slug,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=get_role_permissions(user.role),
    )
