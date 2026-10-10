import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.platform import Tenant, VoiceSession
from app.core.security import (
    create_websocket_ticket,
    get_role_permissions,
    PUBLIC_WIDGET_ALLOWED_TOOLS,
    PERM_VOICE_SESSION_CREATE,
)
from app.api.deps import get_current_user, require_permissions
from config import settings

logger = logging.getLogger("voicedesk.routers.voice_sessions")
router = APIRouter(tags=["Voice Session Tickets"])


class PublicWidgetSessionRequest(BaseModel):
    tenant_slug: str = Field(..., description="Target tenant slug, e.g. sai-smile")
    language: Optional[str] = Field(default="mr", description="Initial language preference")


class InternalVoiceSessionRequest(BaseModel):
    language: Optional[str] = Field(default="mr", description="Voice session language")
    channel: Optional[str] = Field(default="web_voice", description="Channel identifier")


class SessionTicketResponse(BaseModel):
    session_id: str
    ticket: str
    expires_in: int
    tenant_slug: str
    session_type: str  # "public" or "internal"


# ---------------------------------------------------------------------------
# 1. PUBLIC WIDGET SESSION TICKET
# ---------------------------------------------------------------------------

@router.post("/api/v1/widget/session", response_model=SessionTicketResponse)
@router.post("/api/v1/widget/session-ticket", response_model=SessionTicketResponse)
async def create_public_widget_session(
    req: PublicWidgetSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public customer-facing widget session ticket endpoint.
    Used by unauthenticated clinic patients and public website visitors.
    Issues a cryptographically signed ticket strictly restricted to public tools.
    """
    stmt = select(Tenant).where(Tenant.slug == req.tenant_slug.strip().lower(), Tenant.is_active.is_(True))
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{req.tenant_slug}' was not found or is inactive",
        )

    session_id = uuid.uuid4()

    # Record public voice session in PostgreSQL
    voice_session = VoiceSession(
        id=session_id,
        tenant_id=tenant.id,
        user_id=None,
        channel="public_widget",
        language_preference=req.language or tenant.primary_language,
        is_active=True,
    )
    db.add(voice_session)
    await db.commit()

    # Generate ticket restricted to public tools only
    ticket = create_websocket_ticket(
        session_id=str(session_id),
        tenant_id=str(tenant.id),
        tenant_slug=tenant.slug,
        session_type="public",
        user_id=None,
        role="PUBLIC_VISITOR",
        allowed_tools=sorted(list(PUBLIC_WIDGET_ALLOWED_TOOLS)),
    )

    return SessionTicketResponse(
        session_id=str(session_id),
        ticket=ticket,
        expires_in=settings.WS_TICKET_EXPIRE_SECONDS,
        tenant_slug=tenant.slug,
        session_type="public",
    )


# ---------------------------------------------------------------------------
# 2. AUTHENTICATED INTERNAL OPERATOR VOICE SESSION TICKET
# ---------------------------------------------------------------------------

@router.post("/api/v1/voice/session", response_model=SessionTicketResponse)
@router.post("/api/v1/voice/session-ticket", response_model=SessionTicketResponse)
async def create_internal_voice_session(
    req: Optional[InternalVoiceSessionRequest] = None,
    user_and_tenant = Depends(require_permissions(PERM_VOICE_SESSION_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticated internal business operator voice session ticket endpoint.
    Used by authenticated clinic staff, owners, and operators.
    Issues a ticket bound to the user's role and full permitted action catalog.
    """
    user, tenant = user_and_tenant
    session_id = uuid.uuid4()
    lang = req.language if req and req.language else tenant.primary_language
    channel = req.channel if req and req.channel else "operator_app"

    # Record internal voice session in PostgreSQL
    voice_session = VoiceSession(
        id=session_id,
        tenant_id=tenant.id,
        user_id=user.id,
        channel=channel,
        language_preference=lang,
        is_active=True,
    )
    db.add(voice_session)
    await db.commit()

    ticket = create_websocket_ticket(
        session_id=str(session_id),
        tenant_id=str(tenant.id),
        tenant_slug=tenant.slug,
        session_type="internal",
        user_id=str(user.id),
        role=user.role,
        allowed_tools=None,  # Internal users use their full role permissions
    )

    return SessionTicketResponse(
        session_id=str(session_id),
        ticket=ticket,
        expires_in=settings.WS_TICKET_EXPIRE_SECONDS,
        tenant_slug=tenant.slug,
        session_type="internal",
    )
