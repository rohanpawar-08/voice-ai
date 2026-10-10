import json
import logging
import time
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import ActionExecution, ActionStatus, Tenant
from app.engine.context import ExecutionContext
from app.engine.schemas import ActionRequest, ActionResult, ActionStatusEnum
from app.engine.registry import ToolRegistry, get_default_registry
from app.engine.confirmation import ConfirmationPolicyEngine
from app.engine.exceptions import (
    ActionNotFoundError,
    InvalidParametersError,
    InvalidStateTransitionError,
    TenantIsolationError,
    TenantNotFoundError,
)

logger = logging.getLogger("voicedesk.engine.pipeline")


class ActionPipeline:
    """
    Deterministic Action Execution Pipeline & Confirmation Engine.
    Enforces tenant context resolution, tool enablement, parameter validation,
    risk evaluation, confirmation policy, idempotency, and audit state persistence.
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        policy_engine: Optional[ConfirmationPolicyEngine] = None,
    ):
        self.registry = registry or get_default_registry()
        self.policy_engine = policy_engine or ConfirmationPolicyEngine()

    async def propose_action(
        self,
        request: ActionRequest,
        context: ExecutionContext,
        db: AsyncSession,
    ) -> ActionResult:
        """
        Processes a structured action proposal from natural speech / LLM.
        Decides whether to execute immediately (Risk 1), require confirmation (Risk 2),
        or block (Risk 3).
        """
        # 1. Resolve & verify active Tenant context
        stmt = select(Tenant).where(Tenant.id == context.tenant_id, Tenant.is_active.is_(True))
        res = await db.execute(stmt)
        tenant = res.scalar_one_or_none()
        if tenant is None:
            raise TenantNotFoundError(f"Active tenant with ID {context.tenant_id} not found.")

        # 2 & 3. Resolve tool and verify tenant tool enablement & permissions
        adapter, manifest = self.registry.resolve_tool(request.tool_id)
        tenant_tool = await self.registry.verify_tenant_tool_enablement(
            tenant_id=context.tenant_id,
            tool_id=request.tool_id,
            db=db,
            caller_role=context.role,
        )

        # 4. Validate and sanitize parameters against concrete Pydantic schemas
        param_model = self.registry.get_parameter_model(request.tool_id)
        if param_model:
            try:
                validated_params = param_model(**request.parameters)
                sanitized_params = validated_params.model_dump()
            except Exception as e:
                raise InvalidParametersError(
                    f"Parameter validation failed for '{request.tool_id}': {str(e)}"
                )
        else:
            sanitized_params = dict(request.parameters)

        # 5 & 6. Evaluate Risk Level & Confirmation Policy
        requires_confirmation, block_reason = self.policy_engine.evaluate_policy(
            manifest=manifest,
            tenant_policy=tenant_tool.confirmation_policy,
            confirmed_by_caller=request.confirmed,
        )

        # If blocked (e.g. Risk 3 CRITICAL operations in voice)
        if block_reason:
            rejected_exec = ActionExecution(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                session_id=context.session_id,
                tool_id=request.tool_id,
                intent_detected=request.intent,
                extracted_parameters=request.parameters,
                sanitized_parameters=sanitized_params,
                status=ActionStatus.REJECTED.value,
                risk_level=manifest.risk_level,
                idempotency_key=request.idempotency_key,
                error_message=block_reason,
            )
            db.add(rejected_exec)
            await db.commit()
            await db.refresh(rejected_exec)

            return ActionResult(
                execution_id=rejected_exec.id,
                status=ActionStatusEnum.REJECTED,
                tool_id=request.tool_id,
                message=block_reason,
                requires_confirmation=False,
                error_code="CRITICAL_ACTION_BLOCKED",
            )

        # 9. Idempotency Check (if caller provided idempotency_key)
        if request.idempotency_key:
            idemp_stmt = select(ActionExecution).where(
                ActionExecution.tenant_id == context.tenant_id,
                ActionExecution.idempotency_key == request.idempotency_key,
            )
            existing = (await db.execute(idemp_stmt)).scalar_one_or_none()
            if existing:
                if existing.status == ActionStatus.SUCCESS.value:
                    return ActionResult(
                        execution_id=existing.id,
                        status=ActionStatusEnum.SUCCESS,
                        tool_id=existing.tool_id,
                        message="Idempotent duplicate request returned existing successful result.",
                        requires_confirmation=False,
                        result=existing.execution_result,
                    )
                elif existing.status == ActionStatus.PENDING_CONFIRMATION.value:
                    prompt = self.policy_engine.generate_confirmation_prompt(
                        request.tool_id, existing.sanitized_parameters, context.language
                    )
                    return ActionResult(
                        execution_id=existing.id,
                        status=ActionStatusEnum.PENDING_CONFIRMATION,
                        tool_id=existing.tool_id,
                        message="Pending action already exists awaiting confirmation.",
                        requires_confirmation=True,
                        confirmation_prompt=prompt,
                    )
                elif existing.status == ActionStatus.EXECUTING.value:
                    return ActionResult(
                        execution_id=existing.id,
                        status=ActionStatusEnum.EXECUTING,
                        tool_id=existing.tool_id,
                        message="Action is currently executing.",
                        requires_confirmation=False,
                    )

        # 7 & 8. If confirmation required (Risk 2 default) -> Create PENDING_CONFIRMATION
        if requires_confirmation:
            prompt = self.policy_engine.generate_confirmation_prompt(
                tool_id=request.tool_id,
                sanitized_params=sanitized_params,
                language=context.language,
            )

            pending_exec = ActionExecution(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                session_id=context.session_id,
                tool_id=request.tool_id,
                intent_detected=request.intent,
                extracted_parameters=request.parameters,
                sanitized_parameters=sanitized_params,
                status=ActionStatus.PENDING_CONFIRMATION.value,
                risk_level=manifest.risk_level,
                idempotency_key=request.idempotency_key,
            )
            db.add(pending_exec)
            await db.commit()
            await db.refresh(pending_exec)

            # Return without executing adapter
            return ActionResult(
                execution_id=pending_exec.id,
                status=ActionStatusEnum.PENDING_CONFIRMATION,
                tool_id=request.tool_id,
                message="Action requires confirmation before execution.",
                requires_confirmation=True,
                confirmation_prompt=prompt,
            )

        # 10 & 11. No confirmation required (Risk 1 READ) -> Execute immediately
        executing = ActionExecution(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            session_id=context.session_id,
            tool_id=request.tool_id,
            intent_detected=request.intent,
            extracted_parameters=request.parameters,
            sanitized_parameters=sanitized_params,
            status=ActionStatus.EXECUTING.value,
            risk_level=manifest.risk_level,
            idempotency_key=request.idempotency_key,
        )
        db.add(executing)
        await db.commit()
        await db.refresh(executing)

        start_t = time.perf_counter()
        try:
            raw_result = await adapter.execute_tool(
                tool_name=request.tool_id,
                params=sanitized_params,
                context=context.model_dump(),
            )
            duration_ms = int((time.perf_counter() - start_t) * 1000)

            # Parse stringified json result if applicable
            parsed_result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
            final_result = parsed_result if isinstance(parsed_result, dict) else {"output": parsed_result}

            executing.status = ActionStatus.SUCCESS.value
            executing.execution_result = final_result
            executing.execution_duration_ms = duration_ms
            await db.commit()

            return ActionResult(
                execution_id=executing.id,
                status=ActionStatusEnum.SUCCESS,
                tool_id=request.tool_id,
                message="Action executed successfully.",
                requires_confirmation=False,
                result=final_result,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_t) * 1000)
            logger.error(f"Execution error executing tool '{request.tool_id}': {exc}", exc_info=True)
            executing.status = ActionStatus.FAILED.value
            executing.error_message = str(exc)
            executing.execution_duration_ms = duration_ms
            await db.commit()

            return ActionResult(
                execution_id=executing.id,
                status=ActionStatusEnum.FAILED,
                tool_id=request.tool_id,
                message=f"Action execution failed: {str(exc)}",
                requires_confirmation=False,
                error_code="EXECUTION_FAILED",
            )

    async def confirm_action(
        self,
        execution_id: uuid.UUID,
        context: ExecutionContext,
        db: AsyncSession,
    ) -> ActionResult:
        """
        Executes a previously staged PENDING_CONFIRMATION action.
        Uses PostgreSQL row-locking (FOR UPDATE) to prevent concurrent double-executions.
        Uses stored sanitized parameters ONLY (never trusts new client parameters).
        """
        # Acquire row lock
        stmt = (
            select(ActionExecution)
            .where(ActionExecution.id == execution_id)
            .with_for_update()
        )
        res = await db.execute(stmt)
        action = res.scalar_one_or_none()

        if action is None:
            raise ActionNotFoundError(f"Action execution '{execution_id}' not found.")

        # Mandatory Tenant Isolation check
        if action.tenant_id != context.tenant_id:
            raise TenantIsolationError(
                f"Action execution belongs to tenant {action.tenant_id}, not {context.tenant_id}."
            )

        # Idempotent re-confirmation: if already succeeded, return existing result
        if action.status == ActionStatus.SUCCESS.value:
            return ActionResult(
                execution_id=action.id,
                status=ActionStatusEnum.SUCCESS,
                tool_id=action.tool_id,
                message="Action was already confirmed and executed successfully.",
                requires_confirmation=False,
                result=action.execution_result,
            )

        # State transition validation
        if action.status in (ActionStatus.REJECTED.value, ActionStatus.FAILED.value):
            raise InvalidStateTransitionError(
                f"Cannot confirm action with terminal status '{action.status}'."
            )

        if action.status == ActionStatus.EXECUTING.value:
            return ActionResult(
                execution_id=action.id,
                status=ActionStatusEnum.EXECUTING,
                tool_id=action.tool_id,
                message="Action is already currently being executed.",
                requires_confirmation=False,
            )

        if action.status != ActionStatus.PENDING_CONFIRMATION.value:
            raise InvalidStateTransitionError(
                f"Cannot confirm action in status '{action.status}'. Must be PENDING_CONFIRMATION."
            )

        # Verify tool is still enabled
        adapter, _ = self.registry.resolve_tool(action.tool_id)
        await self.registry.verify_tenant_tool_enablement(
            tenant_id=context.tenant_id,
            tool_id=action.tool_id,
            db=db,
            caller_role=context.role,
        )

        # Mark EXECUTING and flush (holding row lock across adapter execution)
        action.status = ActionStatus.EXECUTING.value
        await db.flush()

        # Execute through Domain Adapter using strictly stored sanitized parameters
        start_t = time.perf_counter()
        try:
            raw_result = await adapter.execute_tool(
                tool_name=action.tool_id,
                params=action.sanitized_parameters,
                context=context.model_dump(),
            )
            duration_ms = int((time.perf_counter() - start_t) * 1000)

            parsed_result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
            final_result = parsed_result if isinstance(parsed_result, dict) else {"output": parsed_result}

            action.status = ActionStatus.SUCCESS.value
            action.execution_result = final_result
            action.execution_duration_ms = duration_ms
            await db.commit()

            return ActionResult(
                execution_id=action.id,
                status=ActionStatusEnum.SUCCESS,
                tool_id=action.tool_id,
                message="Confirmed action executed successfully.",
                requires_confirmation=False,
                result=final_result,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_t) * 1000)
            logger.error(f"Error during confirmed execution of tool '{action.tool_id}': {exc}", exc_info=True)
            action.status = ActionStatus.FAILED.value
            action.error_message = str(exc)
            action.execution_duration_ms = duration_ms
            await db.commit()

            return ActionResult(
                execution_id=action.id,
                status=ActionStatusEnum.FAILED,
                tool_id=action.tool_id,
                message=f"Action execution failed: {str(exc)}",
                requires_confirmation=False,
                error_code="EXECUTION_FAILED",
            )

    async def reject_action(
        self,
        execution_id: uuid.UUID,
        context: ExecutionContext,
        db: AsyncSession,
    ) -> ActionResult:
        """
        Rejects a staged PENDING_CONFIRMATION action.
        Transitions state to REJECTED. Never invokes domain adapter.
        """
        stmt = (
            select(ActionExecution)
            .where(ActionExecution.id == execution_id)
            .with_for_update()
        )
        res = await db.execute(stmt)
        action = res.scalar_one_or_none()

        if action is None:
            raise ActionNotFoundError(f"Action execution '{execution_id}' not found.")

        # Mandatory Tenant Isolation check
        if action.tenant_id != context.tenant_id:
            raise TenantIsolationError(
                f"Action execution belongs to tenant {action.tenant_id}, not {context.tenant_id}."
            )

        if action.status != ActionStatus.PENDING_CONFIRMATION.value:
            raise InvalidStateTransitionError(
                f"Cannot reject action in status '{action.status}'. Must be PENDING_CONFIRMATION."
            )

        action.status = ActionStatus.REJECTED.value
        await db.commit()

        return ActionResult(
            execution_id=action.id,
            status=ActionStatusEnum.REJECTED,
            tool_id=action.tool_id,
            message="Action proposal was rejected.",
            requires_confirmation=False,
            error_code=None,
        )


def get_default_pipeline() -> ActionPipeline:
    """Factory creating ActionPipeline with default registry and policy engine."""
    return ActionPipeline(
        registry=get_default_registry(),
        policy_engine=ConfirmationPolicyEngine(),
    )
