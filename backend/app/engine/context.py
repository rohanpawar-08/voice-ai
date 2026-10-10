import uuid
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.platform import Tenant, User
from app.engine.exceptions import TenantNotFoundError


class ExecutionContext(BaseModel):
    """
    Lightweight contextual descriptor passed to action pipeline & adapters.
    Neutral across all business domains.
    """
    tenant_id: uuid.UUID = Field(..., description="Unique tenant UUID")
    tenant_slug: str = Field(..., description="Tenant unique identifier slug")
    user_id: Optional[uuid.UUID] = Field(default=None, description="Requesting user UUID, if identified")
    role: Optional[str] = Field(default="OPERATOR", description="Caller role (e.g. OPERATOR, MANAGER, VIEWER)")
    language: str = Field(default="mr", description="Active voice/dialogue language, e.g. 'mr', 'en', 'hi'")
    session_id: Optional[uuid.UUID] = Field(default=None, description="Active voice session UUID")
    channel: Optional[str] = Field(default="web_voice", description="Communication channel, e.g. web_voice, telephony")
    request_id: Optional[str] = Field(default=None, description="Unique trace request ID")


async def get_transitional_context(
    db: AsyncSession,
    tenant_slug: str = "sai-smile",
    language: str = "mr",
    session_id: Optional[uuid.UUID] = None,
) -> ExecutionContext:
    """
    Transitional compatibility resolver for V1-01 / V1-02.
    Provides the seeded tenant context until V1-03 introduces full auth/JWT/RBAC.
    """
    stmt = select(Tenant).where(Tenant.slug == tenant_slug)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise TenantNotFoundError(f"Transitional tenant '{tenant_slug}' not found.")

    # Fetch default owner/operator user if present
    user_stmt = select(User).where(User.tenant_id == tenant.id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalars().first()

    return ExecutionContext(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        user_id=user.id if user else None,
        role=user.role if user else "OPERATOR",
        language=language or tenant.primary_language,
        session_id=session_id,
        channel="web_voice",
    )
