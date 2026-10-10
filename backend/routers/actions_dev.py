import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.engine import (
    ActionRequest,
    ActionResult,
    ExecutionContext,
    get_transitional_context,
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

router = APIRouter(prefix="/api/v1/actions", tags=["Dev Internal Actions"])
pipeline = get_default_pipeline()


@router.post("/propose", response_model=ActionResult)
async def propose_action_dev(
    request: ActionRequest,
    tenant_slug: str = Query("sai-smile", description="Transitional tenant slug"),
    db: AsyncSession = Depends(get_db),
):
    """
    [TRANSITIONAL DEV ENDPOINT]
    Proposes an action through the deterministic V1-02 action pipeline.
    """
    try:
        context = await get_transitional_context(db=db, tenant_slug=tenant_slug)
        result = await pipeline.propose_action(request, context, db)
        return result
    except (UnknownToolError, ToolDisabledError, InvalidParametersError, PermissionDeniedError) as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.post("/{execution_id}/confirm", response_model=ActionResult)
async def confirm_action_dev(
    execution_id: uuid.UUID,
    tenant_slug: str = Query("sai-smile", description="Transitional tenant slug"),
    db: AsyncSession = Depends(get_db),
):
    """
    [TRANSITIONAL DEV ENDPOINT]
    Confirms a previously staged PENDING_CONFIRMATION action.
    """
    try:
        context = await get_transitional_context(db=db, tenant_slug=tenant_slug)
        result = await pipeline.confirm_action(execution_id, context, db)
        return result
    except ActionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": str(e)})
    except (InvalidStateTransitionError, TenantIsolationError) as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.post("/{execution_id}/reject", response_model=ActionResult)
async def reject_action_dev(
    execution_id: uuid.UUID,
    tenant_slug: str = Query("sai-smile", description="Transitional tenant slug"),
    db: AsyncSession = Depends(get_db),
):
    """
    [TRANSITIONAL DEV ENDPOINT]
    Rejects a staged PENDING_CONFIRMATION action.
    """
    try:
        context = await get_transitional_context(db=db, tenant_slug=tenant_slug)
        result = await pipeline.reject_action(execution_id, context, db)
        return result
    except ActionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": str(e)})
    except (InvalidStateTransitionError, TenantIsolationError) as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})
