import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.models.platform import (
    Tenant,
    ToolDefinition,
    TenantEnabledTool,
    ActionExecution,
    ActionStatus,
    RiskLevel,
)
from app.adapters.base import BaseDomainAdapter, ToolManifest
from app.adapters.healthcare import HealthcareAdapter
from app.engine import (
    ActionPipeline,
    ActionRequest,
    ActionResult,
    ActionStatusEnum,
    ExecutionContext,
    ToolRegistry,
    ConfirmationPolicyEngine,
    get_default_pipeline,
    get_transitional_context,
    UnknownToolError,
    ToolDisabledError,
    InvalidParametersError,
    CriticalActionBlockedError,
    InvalidStateTransitionError,
    TenantIsolationError,
    ActionNotFoundError,
)


@pytest.fixture
async def sai_smile_context(db_session):
    """Provides validated transitional execution context for Tenant 1 (Sai Smile)."""
    return await get_transitional_context(db=db_session, tenant_slug="sai-smile", language="mr")


@pytest.fixture
async def isolated_tenants(db_session):
    """Creates two isolated test tenants for multi-tenant security verification."""
    slug_a = f"tenant-a-{uuid.uuid4().hex[:6]}"
    slug_b = f"tenant-b-{uuid.uuid4().hex[:6]}"

    t_a = Tenant(slug=slug_a, name="Alpha Clinic", domain_type="healthcare", primary_language="mr")
    t_b = Tenant(slug=slug_b, name="Beta Clinic", domain_type="healthcare", primary_language="en")
    db_session.add_all([t_a, t_b])
    await db_session.commit()

    # Enable clinic.check_service_info on both
    enabled_a = TenantEnabledTool(tenant_id=t_a.id, tool_id="clinic.check_service_info", is_enabled=True)
    enabled_b = TenantEnabledTool(tenant_id=t_b.id, tool_id="clinic.check_service_info", is_enabled=False)
    enabled_b_book = TenantEnabledTool(tenant_id=t_b.id, tool_id="clinic.book_appointment", is_enabled=True)
    enabled_a_book = TenantEnabledTool(tenant_id=t_a.id, tool_id="clinic.book_appointment", is_enabled=True)
    db_session.add_all([enabled_a, enabled_b, enabled_a_book, enabled_b_book])
    await db_session.commit()

    ctx_a = ExecutionContext(tenant_id=t_a.id, tenant_slug=t_a.slug, language="mr")
    ctx_b = ExecutionContext(tenant_id=t_b.id, tenant_slug=t_b.slug, language="en")

    yield {"tenant_a": t_a, "tenant_b": t_b, "ctx_a": ctx_a, "ctx_b": ctx_b}

    # Cleanup
    await db_session.delete(t_a)
    await db_session.delete(t_b)
    await db_session.commit()


# ===========================================================================
# 1. TOOL REGISTRY TESTS
# ===========================================================================

def test_01_registry_known_tool_resolves():
    """Verify known enabled tool resolves cleanly from registry."""
    pipeline = get_default_pipeline()
    adapter, manifest = pipeline.registry.resolve_tool("clinic.check_service_info")
    assert adapter.domain_key == "healthcare"
    assert manifest.name == "clinic.check_service_info"
    assert manifest.risk_level == 1


def test_02_registry_unknown_tool_rejected():
    """Verify unknown tool ID raises UnknownToolError."""
    pipeline = get_default_pipeline()
    with pytest.raises(UnknownToolError) as exc_info:
        pipeline.registry.resolve_tool("clinic.nonexistent_tool")
    assert "unknown" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_03_registry_disabled_tenant_tool_rejected(db_session, isolated_tenants):
    """Verify disabled tool for a specific tenant raises ToolDisabledError."""
    pipeline = get_default_pipeline()
    ctx_b = isolated_tenants["ctx_b"]

    with pytest.raises(ToolDisabledError):
        await pipeline.registry.verify_tenant_tool_enablement(
            tenant_id=ctx_b.tenant_id,
            tool_id="clinic.check_service_info",
            db=db_session,
        )


def test_04_registry_healthcare_tools_map_to_adapter():
    """Verify healthcare tools map to HealthcareAdapter."""
    pipeline = get_default_pipeline()
    for tool_id in ["clinic.check_service_info", "clinic.check_available_slots", "clinic.book_appointment"]:
        adapter, manifest = pipeline.registry.resolve_tool(tool_id)
        assert isinstance(adapter, HealthcareAdapter)
        assert manifest.name == tool_id


# ===========================================================================
# 2. PARAMETER VALIDATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_05_validation_valid_parameters_accepted(db_session, sai_smile_context):
    """Verify valid parameters pass schema sanitization and execute."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "cleaning"},
    )
    result = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert result.status == ActionStatusEnum.SUCCESS
    assert result.result is not None


@pytest.mark.asyncio
async def test_06_validation_missing_required_param_rejected(db_session, sai_smile_context):
    """Verify missing required parameter raises InvalidParametersError."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={},  # Missing 'service_name'
    )
    with pytest.raises(InvalidParametersError):
        await pipeline.propose_action(req, sai_smile_context, db_session)


@pytest.mark.asyncio
async def test_07_validation_empty_parameter_rejected(db_session, sai_smile_context):
    """Verify whitespace or empty parameter values are rejected."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "   "},
    )
    with pytest.raises(InvalidParametersError):
        await pipeline.propose_action(req, sai_smile_context, db_session)


@pytest.mark.asyncio
async def test_08_validation_sanitized_parameters_saved(db_session, sai_smile_context):
    """Verify sanitized parameters are saved without extraneous leading/trailing whitespace."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "  cleaning  "},
    )
    result = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert result.status == ActionStatusEnum.SUCCESS

    # Check database record
    exec_row = await db_session.get(ActionExecution, result.execution_id)
    assert exec_row.extracted_parameters["service_name"] == "  cleaning  "
    assert exec_row.sanitized_parameters["service_name"] == "cleaning"

    # Cleanup
    await db_session.delete(exec_row)
    await db_session.commit()


# ===========================================================================
# 3. RISK & CONFIRMATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_09_risk_1_executes_immediately(db_session, sai_smile_context):
    """Verify Risk 1 actions execute immediately with requires_confirmation=False."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_available_slots",
        intent="CHECK_SLOTS",
        parameters={"date": "tomorrow"},
    )
    res = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res.status == ActionStatusEnum.SUCCESS
    assert res.requires_confirmation is False
    assert res.result is not None

    # Cleanup
    exec_row = await db_session.get(ActionExecution, res.execution_id)
    if exec_row:
        await db_session.delete(exec_row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_10_risk_2_creates_pending_confirmation_and_does_not_call_adapter(db_session, sai_smile_context):
    """Verify Risk 2 write action creates PENDING_CONFIRMATION and never calls adapter before confirm."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Rahul Deshmukh",
            "phone": "9876543210",
            "date": "2026-10-15",
            "time_slot": "10:30 AM",
            "service": "Dental Checkup",
        },
    )

    with patch.object(HealthcareAdapter, "execute_tool", new_callable=AsyncMock) as mock_exec:
        res = await pipeline.propose_action(req, sai_smile_context, db_session)
        assert res.status == ActionStatusEnum.PENDING_CONFIRMATION
        assert res.requires_confirmation is True
        assert res.confirmation_prompt is not None
        assert "खात्री आहे का" in res.confirmation_prompt or "Rahul Deshmukh" in res.confirmation_prompt
        # Assert adapter was NOT called
        mock_exec.assert_not_called()

    # Cleanup
    exec_row = await db_session.get(ActionExecution, res.execution_id)
    if exec_row:
        await db_session.delete(exec_row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_11_confirming_risk_2_executes_exactly_once(db_session, sai_smile_context):
    """Verify confirming Risk 2 executes adapter with stored parameters."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Pooja Kulkarni",
            "phone": "9811122233",
            "date": "2026-10-16",
            "time_slot": "11:00 AM",
            "service": "Teeth Whitening",
        },
    )

    # 1. Propose
    staged = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert staged.status == ActionStatusEnum.PENDING_CONFIRMATION

    # 2. Confirm
    mock_return = json.dumps({"status": "confirmed", "booking_id": "BK-101", "patient_name": "Pooja Kulkarni"})
    with patch.object(HealthcareAdapter, "execute_tool", new_callable=AsyncMock, return_value=mock_return) as mock_exec:
        confirmed = await pipeline.confirm_action(staged.execution_id, sai_smile_context, db_session)
        assert confirmed.status == ActionStatusEnum.SUCCESS
        assert confirmed.result["booking_id"] == "BK-101"
        mock_exec.assert_called_once()

    # Cleanup
    exec_row = await db_session.get(ActionExecution, staged.execution_id)
    if exec_row:
        await db_session.delete(exec_row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_12_rejecting_risk_2_never_calls_adapter(db_session, sai_smile_context):
    """Verify rejecting Risk 2 transitions to REJECTED and never calls adapter."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Amit Shinde",
            "phone": "9899988877",
            "date": "2026-10-17",
            "time_slot": "02:00 PM",
            "service": "Root Canal",
        },
    )

    staged = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert staged.status == ActionStatusEnum.PENDING_CONFIRMATION

    with patch.object(HealthcareAdapter, "execute_tool", new_callable=AsyncMock) as mock_exec:
        rejected = await pipeline.reject_action(staged.execution_id, sai_smile_context, db_session)
        assert rejected.status == ActionStatusEnum.REJECTED
        mock_exec.assert_not_called()

    # Verify DB status
    row = await db_session.get(ActionExecution, staged.execution_id)
    assert row.status == ActionStatus.REJECTED.value

    # Cleanup
    await db_session.delete(row)
    await db_session.commit()


@pytest.mark.asyncio
async def test_13_risk_3_returns_rejected(db_session, sai_smile_context):
    """Verify Risk 3 CRITICAL operations are unconditionally blocked in V1-02."""
    pipeline = get_default_pipeline()

    # Create temporary Risk 3 tool manifest
    crit_manifest = ToolManifest(
        name="clinic.purge_all_records",
        description="Irreversible destructive action",
        risk_level=3,
        requires_confirmation=True,
    )

    class DummyDestructiveAdapter(BaseDomainAdapter):
        @property
        def domain_key(self):
            return "healthcare"

        def get_supported_tools(self):
            return [crit_manifest]

        async def execute_tool(self, tool_name, params, context=None):
            return {"status": "purged"}

    pipeline.registry.register_adapter(DummyDestructiveAdapter())

    # Enable for tenant in DB
    tool_def = ToolDefinition(
        id="clinic.purge_all_records",
        domain_key="healthcare",
        name="Purge Records",
        description="Destructive",
        risk_level=3,
    )
    db_session.add(tool_def)
    await db_session.flush()

    enabled = TenantEnabledTool(
        tenant_id=sai_smile_context.tenant_id,
        tool_id="clinic.purge_all_records",
        is_enabled=True,
    )
    db_session.add(enabled)
    await db_session.commit()

    req = ActionRequest(
        tool_id="clinic.purge_all_records",
        intent="PURGE_DATA",
        parameters={},
    )
    res = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res.status == ActionStatusEnum.REJECTED
    assert res.error_code == "CRITICAL_ACTION_BLOCKED"

    # Cleanup
    exec_row = await db_session.get(ActionExecution, res.execution_id)
    if exec_row:
        await db_session.delete(exec_row)
    await db_session.delete(enabled)
    await db_session.delete(tool_def)
    await db_session.commit()


# ===========================================================================
# 4. TENANT ISOLATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_14_tenant_a_cannot_confirm_tenant_b_execution(db_session, isolated_tenants):
    """Verify Tenant A cannot confirm or access Tenant B action execution."""
    pipeline = get_default_pipeline()
    ctx_a = isolated_tenants["ctx_a"]
    ctx_b = isolated_tenants["ctx_b"]

    req_b = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Tenant B Patient",
            "phone": "9900011223",
            "date": "2026-10-20",
            "time_slot": "04:00 PM",
            "service": "Consultation",
        },
    )
    staged_b = await pipeline.propose_action(req_b, ctx_b, db_session)

    # Tenant A attempts to confirm Tenant B execution
    with pytest.raises(TenantIsolationError):
        await pipeline.confirm_action(staged_b.execution_id, ctx_a, db_session)

    # Cleanup
    exec_row = await db_session.get(ActionExecution, staged_b.execution_id)
    if exec_row:
        await db_session.delete(exec_row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_15_tenant_cannot_execute_unassigned_or_disabled_tool(db_session, isolated_tenants):
    """Verify Tenant B cannot execute disabled tool."""
    pipeline = get_default_pipeline()
    ctx_b = isolated_tenants["ctx_b"]

    req = ActionRequest(
        tool_id="clinic.check_service_info",  # disabled for Tenant B
        intent="QUERY_INFO",
        parameters={"service_name": "cleaning"},
    )
    with pytest.raises(ToolDisabledError):
        await pipeline.propose_action(req, ctx_b, db_session)


# ===========================================================================
# 5. STATE MACHINE TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_16_cannot_re_execute_terminal_rejected_execution(db_session, sai_smile_context):
    """Verify terminal REJECTED execution cannot be confirmed."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Test Terminal",
            "phone": "9911223344",
            "date": "2026-10-25",
            "time_slot": "10:00 AM",
            "service": "Cleaning",
        },
    )
    staged = await pipeline.propose_action(req, sai_smile_context, db_session)
    await pipeline.reject_action(staged.execution_id, sai_smile_context, db_session)

    with pytest.raises(InvalidStateTransitionError):
        await pipeline.confirm_action(staged.execution_id, sai_smile_context, db_session)

    # Cleanup
    row = await db_session.get(ActionExecution, staged.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_17_confirming_already_successful_execution_returns_idempotently(db_session, sai_smile_context):
    """Verify re-confirming already SUCCESS execution safely returns existing result."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Idempotent Pooja",
            "phone": "9811122233",
            "date": "2026-10-16",
            "time_slot": "11:00 AM",
            "service": "Teeth Whitening",
        },
    )
    staged = await pipeline.propose_action(req, sai_smile_context, db_session)

    mock_res = json.dumps({"status": "confirmed", "booking_id": "BK-999"})
    with patch.object(HealthcareAdapter, "execute_tool", new_callable=AsyncMock, return_value=mock_res):
        res1 = await pipeline.confirm_action(staged.execution_id, sai_smile_context, db_session)
        assert res1.status == ActionStatusEnum.SUCCESS

        # Second confirm
        res2 = await pipeline.confirm_action(staged.execution_id, sai_smile_context, db_session)
        assert res2.status == ActionStatusEnum.SUCCESS
        assert res2.result["booking_id"] == "BK-999"

    # Cleanup
    row = await db_session.get(ActionExecution, staged.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


# ===========================================================================
# 6. IDEMPOTENCY TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_18_idempotency_prevents_duplicate_adapter_execution(db_session, sai_smile_context):
    """Verify duplicate proposal with same idempotency_key returns cached result without invoking adapter."""
    pipeline = get_default_pipeline()
    idemp_key = f"idemp-test-{uuid.uuid4().hex[:8]}"

    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "cleaning"},
        idempotency_key=idemp_key,
    )

    # First call
    res1 = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res1.status == ActionStatusEnum.SUCCESS

    # Second call with same idempotency key
    with patch.object(HealthcareAdapter, "execute_tool", new_callable=AsyncMock) as mock_exec:
        res2 = await pipeline.propose_action(req, sai_smile_context, db_session)
        assert res2.status == ActionStatusEnum.SUCCESS
        assert res2.execution_id == res1.execution_id
        mock_exec.assert_not_called()

    # Cleanup
    row = await db_session.get(ActionExecution, res1.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_19_cross_tenant_independent_idempotency(db_session, isolated_tenants):
    """Verify independent tenants can use identical idempotency keys without collision."""
    pipeline = get_default_pipeline()
    shared_key = f"shared-idemp-{uuid.uuid4().hex[:6]}"
    ctx_a = isolated_tenants["ctx_a"]
    ctx_b = isolated_tenants["ctx_b"]

    req_a = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Patient A",
            "phone": "9900011111",
            "date": "2026-10-21",
            "time_slot": "10:00 AM",
            "service": "Consultation",
        },
        idempotency_key=shared_key,
    )
    req_b = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "Patient B",
            "phone": "9900022222",
            "date": "2026-10-21",
            "time_slot": "10:00 AM",
            "service": "Consultation",
        },
        idempotency_key=shared_key,
    )

    staged_a = await pipeline.propose_action(req_a, ctx_a, db_session)
    staged_b = await pipeline.propose_action(req_b, ctx_b, db_session)

    assert staged_a.execution_id != staged_b.execution_id
    assert staged_a.status == ActionStatusEnum.PENDING_CONFIRMATION
    assert staged_b.status == ActionStatusEnum.PENDING_CONFIRMATION

    # Cleanup
    row_a = await db_session.get(ActionExecution, staged_a.execution_id)
    row_b = await db_session.get(ActionExecution, staged_b.execution_id)
    if row_a:
        await db_session.delete(row_a)
    if row_b:
        await db_session.delete(row_b)
    await db_session.commit()


# ===========================================================================
# 7. CONCURRENCY TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_20_concurrent_confirmations_execute_adapter_exactly_once(sai_smile_context):
    """
    Mandatory Concurrency Test:
    Two concurrent confirmation attempts target the same pending execution.
    PostgreSQL row-level locking guarantees that exactly one executes the adapter.
    """
    pipeline = get_default_pipeline()

    # Stage pending action in initial session
    async with AsyncSessionLocal() as s_init:
        req = ActionRequest(
            tool_id="clinic.book_appointment",
            intent="BOOK_APPOINTMENT",
            parameters={
                "patient_name": "Concurrent Patient",
                "phone": "9812345678",
                "date": "2026-10-22",
                "time_slot": "03:00 PM",
                "service": "Checkup",
            },
        )
        staged = await pipeline.propose_action(req, sai_smile_context, s_init)
        execution_id = staged.execution_id

    mock_counter = MagicMock()
    mock_payload = json.dumps({"status": "confirmed", "booking_id": "BK-CONC"})

    async def mock_execute(*args, **kwargs):
        mock_counter()
        await asyncio.sleep(0.05)  # simulate brief adapter latency
        return mock_payload

    # Run two concurrent confirm tasks using distinct DB sessions
    async def run_confirm():
        async with AsyncSessionLocal() as sess:
            return await pipeline.confirm_action(execution_id, sai_smile_context, sess)

    with patch.object(HealthcareAdapter, "execute_tool", side_effect=mock_execute):
        res1, res2 = await asyncio.gather(run_confirm(), run_confirm())

    # Assert both tasks completed safely and adapter executed exactly once
    assert res1.status in (ActionStatusEnum.SUCCESS, ActionStatusEnum.EXECUTING)
    assert res2.status in (ActionStatusEnum.SUCCESS, ActionStatusEnum.EXECUTING)
    assert (res1.status == ActionStatusEnum.SUCCESS) or (res2.status == ActionStatusEnum.SUCCESS)

    # Critical: adapter executed exactly once despite concurrent racing calls
    assert mock_counter.call_count == 1

    # Cleanup
    async with AsyncSessionLocal() as s_clean:
        row = await s_clean.get(ActionExecution, execution_id)
        if row:
            await s_clean.delete(row)
            await s_clean.commit()


# ===========================================================================
# 8. HEALTHCARE ADAPTER REGRESSION THROUGH PIPELINE
# ===========================================================================

@pytest.mark.asyncio
async def test_21_healthcare_service_info_english_through_pipeline(db_session, sai_smile_context):
    """Verify clinic.check_service_info executes cleanly in English through pipeline."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "root canal"},
    )
    res = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res.status == ActionStatusEnum.SUCCESS
    assert "₹3,500" in res.result.get("price", "")

    # Cleanup
    row = await db_session.get(ActionExecution, res.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_22_healthcare_service_info_marathi_through_pipeline(db_session, sai_smile_context):
    """Verify clinic.check_service_info executes cleanly with Marathi aliases through pipeline."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "दात स्वच्छ करणे"},
    )
    res = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res.status == ActionStatusEnum.SUCCESS
    assert "₹800" in res.result.get("price", "")

    # Cleanup
    row = await db_session.get(ActionExecution, res.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_23_healthcare_check_available_slots_through_pipeline(db_session, sai_smile_context):
    """Verify clinic.check_available_slots executes cleanly through pipeline."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.check_available_slots",
        intent="CHECK_SLOTS",
        parameters={"date": "Tomorrow"},
    )
    res = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res.status == ActionStatusEnum.SUCCESS
    assert "available_slots" in res.result
    assert len(res.result["available_slots"]) > 0

    # Cleanup
    row = await db_session.get(ActionExecution, res.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_24_healthcare_book_appointment_pending_confirmation_through_pipeline(db_session, sai_smile_context):
    """Verify booking request returns PENDING_CONFIRMATION and prompt in Marathi."""
    pipeline = get_default_pipeline()
    req = ActionRequest(
        tool_id="clinic.book_appointment",
        intent="BOOK_APPOINTMENT",
        parameters={
            "patient_name": "विजय शिंदे",
            "phone": "9822099999",
            "date": "2026-10-18",
            "time_slot": "11:30 AM",
            "service": "रूट कॅनाल",
        },
    )
    res = await pipeline.propose_action(req, sai_smile_context, db_session)
    assert res.status == ActionStatusEnum.PENDING_CONFIRMATION
    assert res.requires_confirmation is True
    assert "विजय शिंदे" in res.confirmation_prompt

    # Cleanup
    row = await db_session.get(ActionExecution, res.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_25_dev_api_endpoints_integration(db_session, sai_smile_context):
    """Verify dev API helper flow works as expected."""
    from routers.actions_dev import propose_action_dev, confirm_action_dev, reject_action_dev
    from fastapi import HTTPException

    req = ActionRequest(
        tool_id="clinic.check_service_info",
        intent="QUERY_SERVICE",
        parameters={"service_name": "cleaning"},
    )
    res = await propose_action_dev(req, tenant_slug="sai-smile", db=db_session)
    assert res.status == ActionStatusEnum.SUCCESS

    # Cleanup
    row = await db_session.get(ActionExecution, res.execution_id)
    if row:
        await db_session.delete(row)
        await db_session.commit()
