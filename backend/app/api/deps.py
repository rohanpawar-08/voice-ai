import uuid
from typing import Callable, List, Optional, Tuple
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.platform import Tenant, User
from app.core.security import decode_access_token, has_permission, get_role_permissions
from app.engine.context import ExecutionContext

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> Tuple[User, Tenant]:
    """
    Validates the Bearer JWT token from the Authorization header,
    loads the active User and Tenant from PostgreSQL,
    and returns (user, tenant).
    Raises 401 Unauthorized on missing, invalid, or expired credentials.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    user_id_str = payload.get("sub") or payload.get("user_id")
    tenant_id_str = payload.get("tenant_id")

    if not user_id_str or not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing identity claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(user_id_str)
        tenant_id = uuid.UUID(tenant_id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch User and Tenant together from database
    stmt = (
        select(User, Tenant)
        .join(Tenant, User.tenant_id == Tenant.id)
        .where(User.id == user_id, Tenant.id == tenant_id)
    )
    res = await db.execute(stmt)
    row = res.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or Tenant no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user, tenant = row

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user, tenant


def require_permissions(*required_perms: str) -> Callable:
    """
    Dependency factory enforcing that the authenticated user holds
    the specified platform/tenant permissions.
    Raises 403 Forbidden on insufficient permissions.
    """
    async def permission_checker(
        user_and_tenant: Tuple[User, Tenant] = Depends(get_current_user),
    ) -> Tuple[User, Tenant]:
        user, tenant = user_and_tenant
        for perm in required_perms:
            if not has_permission(user.role, perm):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: role '{user.role}' lacks permission '{perm}'",
                )
        return user, tenant

    return permission_checker


def require_roles(*allowed_roles: str) -> Callable:
    """
    Dependency factory enforcing that the authenticated user
    possesses one of the specified roles.
    """
    async def role_checker(
        user_and_tenant: Tuple[User, Tenant] = Depends(get_current_user),
    ) -> Tuple[User, Tenant]:
        user, tenant = user_and_tenant
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{user.role}' is not in allowed roles {list(allowed_roles)}",
            )
        return user, tenant

    return role_checker


async def get_authenticated_execution_context(
    user_and_tenant: Tuple[User, Tenant] = Depends(get_current_user),
) -> ExecutionContext:
    """
    Builds a secure, server-side ExecutionContext strictly from
    the authenticated User and Tenant.
    Client-provided tenant values are ignored or validated against this authoritative context.
    """
    user, tenant = user_and_tenant
    return ExecutionContext(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        user_id=user.id,
        role=user.role,
        language=tenant.primary_language,
        channel="web_voice",
    )
