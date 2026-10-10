import datetime
import uuid
from datetime import timedelta, timezone
from typing import Any, Dict, List, Optional, Set
import bcrypt
import jwt
from fastapi import HTTPException, status

from config import settings

# ---------------------------------------------------------------------------
# 1. RBAC & PERMISSION CATALOG
# ---------------------------------------------------------------------------
# Domain-neutral platform permissions
PERM_TENANT_READ = "tenant.read"
PERM_TENANT_MANAGE = "tenant.manage"
PERM_USERS_READ = "users.read"
PERM_USERS_MANAGE = "users.manage"
PERM_ACTIONS_READ = "actions.read"
PERM_ACTIONS_EXECUTE = "actions.execute"
PERM_ACTIONS_CONFIRM = "actions.confirm"
PERM_ACTIONS_REJECT = "actions.reject"
PERM_ADMIN_DASHBOARD = "admin.dashboard"
PERM_VOICE_SESSION_CREATE = "voice.session.create"
PERM_APPOINTMENTS_READ = "appointments.read"
PERM_APPOINTMENTS_MANAGE = "appointments.manage"

ROLE_PERMISSIONS_MAP: Dict[str, Set[str]] = {
    "PLATFORM_SUPERADMIN": {
        PERM_TENANT_READ,
        PERM_TENANT_MANAGE,
        PERM_USERS_READ,
        PERM_USERS_MANAGE,
        PERM_ACTIONS_READ,
        PERM_ACTIONS_EXECUTE,
        PERM_ACTIONS_CONFIRM,
        PERM_ACTIONS_REJECT,
        PERM_ADMIN_DASHBOARD,
        PERM_VOICE_SESSION_CREATE,
        PERM_APPOINTMENTS_READ,
        PERM_APPOINTMENTS_MANAGE,
    },
    "TENANT_OWNER": {
        PERM_TENANT_READ,
        PERM_TENANT_MANAGE,
        PERM_USERS_READ,
        PERM_USERS_MANAGE,
        PERM_ACTIONS_READ,
        PERM_ACTIONS_EXECUTE,
        PERM_ACTIONS_CONFIRM,
        PERM_ACTIONS_REJECT,
        PERM_ADMIN_DASHBOARD,
        PERM_VOICE_SESSION_CREATE,
        PERM_APPOINTMENTS_READ,
        PERM_APPOINTMENTS_MANAGE,
    },
    "MANAGER": {
        PERM_TENANT_READ,
        PERM_USERS_READ,
        PERM_ACTIONS_READ,
        PERM_ACTIONS_EXECUTE,
        PERM_ACTIONS_CONFIRM,
        PERM_ACTIONS_REJECT,
        PERM_ADMIN_DASHBOARD,
        PERM_VOICE_SESSION_CREATE,
        PERM_APPOINTMENTS_READ,
        PERM_APPOINTMENTS_MANAGE,
    },
    "OPERATOR": {
        PERM_TENANT_READ,
        PERM_ACTIONS_READ,
        PERM_ACTIONS_EXECUTE,
        PERM_ACTIONS_CONFIRM,
        PERM_ACTIONS_REJECT,
        PERM_VOICE_SESSION_CREATE,
        PERM_APPOINTMENTS_READ,
    },
    "VIEWER": {
        PERM_TENANT_READ,
        PERM_ACTIONS_READ,
        PERM_APPOINTMENTS_READ,
    },
}

# Public customer widget restricted allowed tools
PUBLIC_WIDGET_ALLOWED_TOOLS: Set[str] = {
    "clinic.check_service_info",
    "clinic.check_available_slots",
    "clinic.book_appointment",
}


def get_role_permissions(role: str) -> List[str]:
    """Returns the set of permission keys mapped to a given user role."""
    return sorted(list(ROLE_PERMISSIONS_MAP.get(role, set())))


def has_permission(role: str, permission: str) -> bool:
    """Verifies whether a given role holds a specific permission."""
    perms = ROLE_PERMISSIONS_MAP.get(role, set())
    return permission in perms


# ---------------------------------------------------------------------------
# 2. PASSWORD HASHING (BCRYPT)
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    """Securely hashes a plaintext password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash in constant time."""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 3. JWT ACCESS TOKEN
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    tenant_id: str,
    tenant_slug: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    expires_delta_minutes: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Creates a cryptographically signed, short-lived JWT access token.
    Binds: user_id, tenant_id, tenant_slug, role.
    """
    now = datetime.datetime.now(timezone.utc)
    if expires_delta is not None:
        delta = expires_delta
    elif expires_delta_minutes is not None:
        delta = timedelta(minutes=expires_delta_minutes)
    else:
        delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + delta

    payload = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "tenant_slug": tenant_slug,
        "role": role,
        "permissions": get_role_permissions(role),
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    Raises 401 HTTPException on signature mismatch, expiration, or invalid token type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("token_type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type: expected access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# 4. WEBSOCKET SESSION TICKETS
# ---------------------------------------------------------------------------

def create_websocket_ticket(
    session_id: str,
    tenant_id: str,
    tenant_slug: str,
    session_type: str = "public",  # "public" or "internal"
    user_id: Optional[str] = None,
    role: Optional[str] = None,
    allowed_tools: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
    expires_seconds: Optional[int] = None,
) -> str:
    """
    Generates a cryptographically signed, short-lived WebSocket session ticket.
    Binds: session_id, tenant_id, tenant_slug, session_type, allowed tools.
    """
    now = datetime.datetime.now(timezone.utc)
    if expires_delta is not None:
        delta = expires_delta
    elif expires_seconds is not None:
        delta = timedelta(seconds=expires_seconds)
    else:
        delta = timedelta(seconds=settings.WS_TICKET_EXPIRE_SECONDS)
    expire = now + delta

    # If public, tools are strictly constrained to PUBLIC_WIDGET_ALLOWED_TOOLS
    if session_type == "public":
        tools = sorted(list(PUBLIC_WIDGET_ALLOWED_TOOLS))
    else:
        tools = allowed_tools or []

    payload = {
        "sub": str(session_id),
        "session_id": str(session_id),
        "tenant_id": str(tenant_id),
        "tenant_slug": tenant_slug,
        "session_type": session_type,
        "user_id": str(user_id) if user_id else None,
        "role": role if role else "PUBLIC",
        "allowed_tools": tools,
        "token_type": "websocket_ticket",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    ticket = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return ticket


def decode_websocket_ticket(ticket: str) -> Dict[str, Any]:
    """
    Decodes and validates a WebSocket session ticket.
    Returns decoded payload or raises ValueError with safe deterministic error message.
    """
    try:
        payload = jwt.decode(
            ticket,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("token_type") != "websocket_ticket":
            raise ValueError("Invalid ticket type")
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Ticket has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid or tampered ticket")


# ---------------------------------------------------------------------------
# 5. LOGIN RATE LIMITING (REDIS)
# ---------------------------------------------------------------------------

async def check_login_rate_limit(redis_client, identity: str, max_attempts: int = 5, window_seconds: int = 600) -> None:
    """
    Guards against brute-force password guessing attacks using Redis.
    Limits failed attempts to max_attempts per window_seconds.
    """
    if redis_client is None:
        return
    try:
        key = f"auth:failed_attempts:{identity.lower().strip()}"
        attempts_str = await redis_client.get(key)
        if attempts_str and int(attempts_str) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again after 10 minutes.",
            )
    except HTTPException:
        raise
    except Exception:
        pass


async def record_login_failure(redis_client, identity: str, window_seconds: int = 600) -> None:
    """Increments the failed login attempt counter in Redis."""
    if redis_client is None:
        return
    try:
        key = f"auth:failed_attempts:{identity.lower().strip()}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window_seconds)
    except Exception:
        pass


async def reset_login_failures(redis_client, identity: str) -> None:
    """Resets the failed login attempt counter upon successful authentication."""
    if redis_client is None:
        return
    try:
        key = f"auth:failed_attempts:{identity.lower().strip()}"
        await redis_client.delete(key)
    except Exception:
        pass
