import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Dialect-adaptive JSON type (JSONB on PostgreSQL, JSON fallback elsewhere)
JSONType = JSONB().with_variant(JSON(), "sqlite").with_variant(JSON(), "default")


class DomainType(str, enum.Enum):
    HEALTHCARE = "healthcare"
    RETAIL = "retail"
    DAIRY = "dairy"
    RESTAURANT = "restaurant"
    SALON = "salon"
    GENERIC = "generic"


class UserRole(str, enum.Enum):
    PLATFORM_SUPERADMIN = "PLATFORM_SUPERADMIN"
    TENANT_OWNER = "TENANT_OWNER"
    MANAGER = "MANAGER"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class ActionStatus(str, enum.Enum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class RiskLevel(int, enum.Enum):
    READ = 1
    NORMAL_WRITE = 2
    CRITICAL = 3


# ---------------------------------------------------------------------------
# 1. Tenant
# ---------------------------------------------------------------------------
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_type: Mapped[str] = mapped_column(String(64), default=DomainType.GENERIC.value, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    primary_language: Mapped[str] = mapped_column(String(16), default="mr", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    enabled_tools: Mapped[List["TenantEnabledTool"]] = relationship(
        "TenantEnabledTool", back_populates="tenant", cascade="all, delete-orphan"
    )
    voice_sessions: Mapped[List["VoiceSession"]] = relationship(
        "VoiceSession", back_populates="tenant", cascade="all, delete-orphan"
    )
    action_executions: Mapped[List["ActionExecution"]] = relationship(
        "ActionExecution", back_populates="tenant", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 2. User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_tenant_email", "tenant_id", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), default=UserRole.OPERATOR.value, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    voice_sessions: Mapped[List["VoiceSession"]] = relationship("VoiceSession", back_populates="user")
    action_executions: Mapped[List["ActionExecution"]] = relationship("ActionExecution", back_populates="user")


# ---------------------------------------------------------------------------
# 3. ToolDefinition
# ---------------------------------------------------------------------------
class ToolDefinition(Base):
    __tablename__ = "tool_definitions"

    # Tool identifier key, e.g. "clinic.check_service_info", "clinic.book_appointment"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    domain_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[int] = mapped_column(Integer, default=RiskLevel.READ.value, nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parameters_schema: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    is_global_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant_assignments: Mapped[List["TenantEnabledTool"]] = relationship(
        "TenantEnabledTool", back_populates="tool_definition", cascade="all, delete-orphan"
    )
    action_executions: Mapped[List["ActionExecution"]] = relationship(
        "ActionExecution", back_populates="tool_definition"
    )


# ---------------------------------------------------------------------------
# 4. TenantEnabledTool (Composite Primary Key: tenant_id + tool_id)
# ---------------------------------------------------------------------------
class TenantEnabledTool(Base):
    __tablename__ = "tenant_enabled_tools"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    tool_id: Mapped[str] = mapped_column(
        ForeignKey("tool_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confirmation_policy: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="enabled_tools")
    tool_definition: Mapped["ToolDefinition"] = relationship("ToolDefinition", back_populates="tenant_assignments")


# ---------------------------------------------------------------------------
# 5. VoiceSession
# ---------------------------------------------------------------------------
class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(64), default="web_voice", nullable=False)
    language_preference: Mapped[str] = mapped_column(String(16), default="mr", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="voice_sessions")
    user: Mapped["User"] = relationship("User", back_populates="voice_sessions")
    action_executions: Mapped[List["ActionExecution"]] = relationship(
        "ActionExecution", back_populates="session"
    )


# ---------------------------------------------------------------------------
# 6. ActionExecution
# ---------------------------------------------------------------------------
class ActionExecution(Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        Index(
            "uq_action_executions_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voice_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_id: Mapped[str] = mapped_column(
        ForeignKey("tool_definitions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    intent_detected: Mapped[str] = mapped_column(String(128), nullable=False)
    extracted_parameters: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    sanitized_parameters: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ActionStatus.PENDING_CONFIRMATION.value, nullable=False, index=True
    )
    risk_level: Mapped[int] = mapped_column(Integer, default=RiskLevel.READ.value, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=True, index=True)
    execution_result: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    execution_duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="action_executions")
    session: Mapped["VoiceSession"] = relationship("VoiceSession", back_populates="action_executions")
    user: Mapped["User"] = relationship("User", back_populates="action_executions")
    tool_definition: Mapped["ToolDefinition"] = relationship(
        "ToolDefinition", back_populates="action_executions"
    )
