import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.platform import Tenant, User
from app.engine import (
    ActionRequest,
    ActionResult,
    ExecutionContext,
    get_default_pipeline,
    ActionEngineError,
    TenantIsolationError,
    InvalidStateTransitionError,
    ActionNotFoundError,
    InvalidParametersError,
    UnknownToolError,
    ToolDisabledError,
    PermissionDeniedError,
)
from app.api.deps import (
    get_current_user,
    get_authenticated_execution_context,
    require_permissions,
)
from app.core.security import (
    PERM_ACTIONS_EXECUTE,
    PERM_ACTIONS_CONFIRM,
    PERM_ACTIONS_REJECT,
)

logger = logging.getLogger("voicedesk.routers.actions")
router = APIRouter(prefix="/api/v1/actions", tags=["Protected Action Execution"])
pipeline = get_default_pipeline()


@router.post("/propose", response_model=ActionResult)
async def propose_action(
    request: ActionRequest,
    context: ExecutionContext = Depends(get_authenticated_execution_context),
    user_and_tenant = Depends(require_permissions(PERM_ACTIONS_EXECUTE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticated action proposal endpoint.
    Processes structured natural speech action proposals through the deterministic
    validation, tenant enablement, risk classification, and confirmation engine.
    """
    try:
        result = await pipeline.propose_action(request, context, db)
        return result
    except (UnknownToolError, ToolDisabledError, InvalidParametersError, PermissionDeniedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        logger.error(f"Error in propose_action: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Action proposal execution failed"},
        )


@router.post("/{execution_id}/confirm", response_model=ActionResult)
async def confirm_action(
    execution_id: uuid.UUID,
    context: ExecutionContext = Depends(get_authenticated_execution_context),
    user_and_tenant = Depends(require_permissions(PERM_ACTIONS_CONFIRM)),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticated action confirmation endpoint.
    Executes a previously staged PENDING_CONFIRMATION action.
    Strictly enforces tenant isolation, row locks, and immutable parameters.
    """
    try:
        result = await pipeline.confirm_action(execution_id, context, db)
        return result
    except ActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": e.code, "message": str(e)})
    except TenantIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": e.code, "message": str(e)})
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        logger.error(f"Error in confirm_action: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Action confirmation failed"},
        )


@router.post("/{execution_id}/reject", response_model=ActionResult)
async def reject_action(
    execution_id: uuid.UUID,
    context: ExecutionContext = Depends(get_authenticated_execution_context),
    user_and_tenant = Depends(require_permissions(PERM_ACTIONS_REJECT)),
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticated action rejection endpoint.
    Transitions a staged PENDING_CONFIRMATION action to REJECTED.
    """
    try:
        result = await pipeline.reject_action(execution_id, context, db)
        return result
    except ActionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": e.code, "message": str(e)})
    except TenantIsolationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": e.code, "message": str(e)})
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        logger.error(f"Error in reject_action: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Action rejection failed"},
        )
