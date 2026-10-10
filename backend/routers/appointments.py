import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_permissions, require_roles
from app.core.security import PERM_APPOINTMENTS_READ
from config import settings
from routers import ws_copilot
from agent.tools import get_all_appointments

logger = logging.getLogger("voicedesk.routers.appointments")
router = APIRouter(prefix="/api/appointments", tags=["Clinic Appointments Admin"])


@router.get("")
async def get_clinic_appointments(
    user_and_tenant = Depends(require_permissions(PERM_APPOINTMENTS_READ)),
):
    """
    Authenticated, tenant-scoped endpoint returning booked clinic appointments
    for authorized operators and managers.
    Prevents cross-tenant appointment exposure.
    """
    user, tenant = user_and_tenant

    appointments = []
    try:
        r = await ws_copilot.get_redis_client()
        # Tenant-scoped appointments key
        raw_list = await r.lrange(f"clinic:{tenant.id}:appointments", 0, -1)
        for item in raw_list:
            try:
                appointments.append(json.loads(item))
            except Exception:
                pass

        # Compatibility bridge for tenant 1 (Sai Smile) legacy key
        if len(appointments) == 0 and tenant.slug == "sai-smile":
            appointments = get_all_appointments()
    except Exception as e:
        logger.warning(f"Error reading appointments for tenant {tenant.id}: {e}")
        appointments = []

    return {
        "status": "success",
        "tenant_id": str(tenant.id),
        "total": len(appointments),
        "appointments": appointments,
    }


@router.delete("")
async def clear_clinic_appointments(
    user_and_tenant = Depends(require_roles("PLATFORM_SUPERADMIN")),
):
    """
    Restricted development reset endpoint.
    Strictly forbidden in production environments.
    Only PLATFORM_SUPERADMIN can execute in development.
    """
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk appointment deletion is disabled in non-development environments",
        )

    user, tenant = user_and_tenant
    try:
        r = await ws_copilot.get_redis_client()
        await r.delete(f"clinic:{tenant.id}:appointments")
        if tenant.slug == "sai-smile":
            await r.delete("clinic:appointments")
        return {
            "status": "success",
            "message": f"Cleared appointments for tenant {tenant.slug} in development mode",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
