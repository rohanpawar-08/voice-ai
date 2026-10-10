import json
import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal, check_db_health
from app.models.platform import (
    Tenant,
    User,
    ToolDefinition,
    TenantEnabledTool,
    VoiceSession,
    ActionExecution,
    DomainType,
    ActionStatus,
    RiskLevel,
)
from app.adapters.healthcare import HealthcareAdapter
from app.core.seed import seed_initial_data
import agent.tools as clinic_tools


@pytest.mark.asyncio
async def test_01_database_connection(db_session):
    """Verify live async connection to PostgreSQL."""
    assert await check_db_health() is True
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_02_tenant_model_crud(db_session):
    """Verify Tenant Create, Read, Update, and Delete operations."""
    test_slug = f"test-tenant-{uuid.uuid4().hex[:8]}"

    # Create
    tenant = Tenant(
        slug=test_slug,
        name="Temporary Test Dental Clinic",
        domain_type=DomainType.HEALTHCARE.value,
        timezone="Asia/Kolkata",
        primary_language="mr",
    )
    db_session.add(tenant)
    await db_session.commit()
    tenant_id = tenant.id

    # Read
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    fetched = (await db_session.execute(stmt)).scalar_one()
    assert fetched.slug == test_slug
    assert fetched.domain_type == "healthcare"

    # Update
    fetched.name = "Updated Test Dental Clinic"
    await db_session.commit()

    stmt = select(Tenant).where(Tenant.id == tenant_id)
    updated = (await db_session.execute(stmt)).scalar_one()
    assert updated.name == "Updated Test Dental Clinic"

    # Delete / Cleanup
    await db_session.delete(updated)
    await db_session.commit()

    stmt = select(Tenant).where(Tenant.id == tenant_id)
    assert (await db_session.execute(stmt)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_03_tool_definition_uniqueness(db_session):
    """Verify ToolDefinition primary key uniqueness constraint."""
    tool_id = f"test.unique.tool.{uuid.uuid4().hex[:6]}"
    t1 = ToolDefinition(
        id=tool_id,
        domain_key="test",
        name="Test Tool",
        description="Testing uniqueness",
        risk_level=1,
        parameters_schema={},
    )
    db_session.add(t1)
    await db_session.commit()

    # In a separate session, duplicate ID must trigger IntegrityError
    async with AsyncSessionLocal() as s2:
        t2 = ToolDefinition(
            id=tool_id,
            domain_key="test",
            name="Duplicate Tool",
            description="Should fail",
            risk_level=1,
            parameters_schema={},
        )
        s2.add(t2)
        with pytest.raises(IntegrityError):
            await s2.commit()

    # Cleanup
    existing = await db_session.get(ToolDefinition, tool_id)
    if existing:
        await db_session.delete(existing)
        await db_session.commit()


@pytest.mark.asyncio
async def test_04_tenant_enabled_tool_mapping(db_session):
    """Verify TenantEnabledTool composite key and relationships."""
    stmt = select(Tenant).where(Tenant.slug == "sai-smile")
    tenant = (await db_session.execute(stmt)).scalar_one()

    stmt = select(TenantEnabledTool).where(TenantEnabledTool.tenant_id == tenant.id)
    mappings = (await db_session.execute(stmt)).scalars().all()
    enabled_ids = [m.tool_id for m in mappings if m.is_enabled]

    assert "clinic.check_service_info" in enabled_ids
    assert "clinic.check_available_slots" in enabled_ids
    assert "clinic.book_appointment" in enabled_ids


@pytest.mark.asyncio
async def test_05_voice_session_persistence(db_session):
    """Verify VoiceSession creation and lookup."""
    stmt = select(Tenant).where(Tenant.slug == "sai-smile")
    tenant = (await db_session.execute(stmt)).scalar_one()

    v_session = VoiceSession(
        tenant_id=tenant.id,
        channel="web_voice",
        language_preference="mr",
        is_active=True,
    )
    db_session.add(v_session)
    await db_session.commit()
    session_id = v_session.id

    stmt = select(VoiceSession).where(VoiceSession.id == session_id)
    fetched = (await db_session.execute(stmt)).scalar_one()
    assert fetched.tenant_id == tenant.id
    assert fetched.channel == "web_voice"
    assert fetched.language_preference == "mr"
    assert fetched.is_active is True

    # Cleanup
    await db_session.delete(fetched)
    await db_session.commit()


@pytest.mark.asyncio
async def test_06_action_execution_persistence(db_session):
    """Verify ActionExecution insertion and field validation."""
    stmt = select(Tenant).where(Tenant.slug == "sai-smile")
    tenant = (await db_session.execute(stmt)).scalar_one()

    action = ActionExecution(
        tenant_id=tenant.id,
        tool_id="clinic.check_service_info",
        intent_detected="query_service_pricing",
        extracted_parameters={"service_name": "cleaning"},
        sanitized_parameters={"service_name": "cleaning"},
        status=ActionStatus.SUCCESS.value,
        risk_level=RiskLevel.READ.value,
        idempotency_key="idemp-" + uuid.uuid4().hex[:12],
        execution_result={"price": "₹800", "duration": "30 minutes"},
        execution_duration_ms=45,
    )
    db_session.add(action)
    await db_session.commit()
    action_id = action.id

    stmt = select(ActionExecution).where(ActionExecution.id == action_id)
    fetched = (await db_session.execute(stmt)).scalar_one()
    assert fetched.tenant_id == tenant.id
    assert fetched.tool_id == "clinic.check_service_info"
    assert fetched.intent_detected == "query_service_pricing"
    assert fetched.extracted_parameters["service_name"] == "cleaning"
    assert fetched.status == "SUCCESS"
    assert fetched.risk_level == 1
    assert fetched.execution_result["price"] == "₹800"

    # Cleanup
    await db_session.delete(fetched)
    await db_session.commit()


@pytest.mark.asyncio
async def test_07_seed_idempotency(db_session):
    """Verify running the seed script multiple times produces no duplicates."""
    res1 = await seed_initial_data()
    res2 = await seed_initial_data()

    assert res1["tenant"] == res2["tenant"]
    assert res1["user"] == res2["user"]

    # Check exactly 1 sai-smile tenant
    stmt = select(Tenant).where(Tenant.slug == "sai-smile")
    tenants = (await db_session.execute(stmt)).scalars().all()
    assert len(tenants) == 1

    # Check exactly 1 admin user for sai-smile
    stmt = select(User).where(User.tenant_id == tenants[0].id)
    users = (await db_session.execute(stmt)).scalars().all()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_08_tenant_isolation(db_session):
    """
    Mandatory: Verify tenant-scoped queries isolate records between Tenant A and Tenant B.
    """
    # Create Tenant A
    tenant_a = Tenant(
        slug=f"tenant-a-{uuid.uuid4().hex[:6]}",
        name="Clinic Alpha",
        domain_type="healthcare",
        primary_language="mr",
    )
    # Create Tenant B
    tenant_b = Tenant(
        slug=f"tenant-b-{uuid.uuid4().hex[:6]}",
        name="Retail Beta",
        domain_type="retail",
        primary_language="en",
    )
    db_session.add_all([tenant_a, tenant_b])
    await db_session.commit()

    # Insert ActionExecution for Tenant A
    action_a = ActionExecution(
        tenant_id=tenant_a.id,
        tool_id="clinic.check_service_info",
        intent_detected="alpha_intent",
        extracted_parameters={"query": "alpha"},
        status="SUCCESS",
    )
    # Insert ActionExecution for Tenant B
    action_b = ActionExecution(
        tenant_id=tenant_b.id,
        tool_id="clinic.check_service_info",
        intent_detected="beta_intent",
        extracted_parameters={"query": "beta"},
        status="SUCCESS",
    )
    db_session.add_all([action_a, action_b])
    await db_session.commit()

    # Query scoped to Tenant A
    stmt_a = select(ActionExecution).where(ActionExecution.tenant_id == tenant_a.id)
    records_a = (await db_session.execute(stmt_a)).scalars().all()
    intents_a = [r.intent_detected for r in records_a]
    assert "alpha_intent" in intents_a
    assert "beta_intent" not in intents_a  # Tenant B records MUST NOT be returned

    # Query scoped to Tenant B
    stmt_b = select(ActionExecution).where(ActionExecution.tenant_id == tenant_b.id)
    records_b = (await db_session.execute(stmt_b)).scalars().all()
    intents_b = [r.intent_detected for r in records_b]
    assert "beta_intent" in intents_b
    assert "alpha_intent" not in intents_b  # Tenant A records MUST NOT be returned

    # Cleanup test tenants (cascades to actions)
    await db_session.delete(tenant_a)
    await db_session.delete(tenant_b)
    await db_session.commit()


@pytest.mark.asyncio
async def test_09_healthcare_adapter_english():
    """Verify HealthcareAdapter English tool execution."""
    adapter = HealthcareAdapter()
    raw = await adapter.execute_tool("clinic.check_service_info", {"service_name": "cleaning"})
    data = json.loads(raw)
    assert "service" in data
    assert "price" in data
    assert "₹800" in data["price"]


@pytest.mark.asyncio
async def test_10_healthcare_adapter_marathi():
    """Verify HealthcareAdapter Marathi alias tool execution."""
    adapter = HealthcareAdapter()
    raw = await adapter.execute_tool("clinic.check_service_info", {"service_name": "दात स्वच्छ करणे"})
    data = json.loads(raw)
    assert "service" in data
    assert "price" in data
    assert "₹800" in data["price"]


def test_11_clinic_tools_direct_callable():
    """Verify original clinic tools remain directly callable with zero regression."""
    info_res = clinic_tools.check_service_info.invoke({"service_name": "root canal"})
    info_data = json.loads(info_res)
    assert "₹3,500" in info_data["price"]

    slots_res = clinic_tools.check_available_slots.invoke({"date": "Tomorrow"})
    slots_data = json.loads(slots_res)
    assert "available_slots" in slots_data
    assert len(slots_data["available_slots"]) > 0
