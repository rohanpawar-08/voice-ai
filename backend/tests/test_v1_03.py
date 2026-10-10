import asyncio
import json
import uuid
import time
import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import select

from main import app
from config import settings
from app.core.database import AsyncSessionLocal
from app.models.platform import (
    Tenant,
    User,
    TenantEnabledTool,
    ActionExecution,
    ActionStatus,
    RiskLevel,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_websocket_ticket,
    decode_websocket_ticket,
    ROLE_PERMISSIONS_MAP,
    PUBLIC_WIDGET_ALLOWED_TOOLS,
    PERM_ACTIONS_EXECUTE,
    PERM_ACTIONS_CONFIRM,
    PERM_APPOINTMENTS_READ,
    check_login_rate_limit,
    record_login_failure,
    reset_login_failures,
)
from app.engine import (
    ActionRequest,
    ActionStatusEnum,
)


@pytest.fixture
async def setup_test_tenants_and_users(db_session):
    """
    Creates two isolated tenants (Tenant Alpha & Tenant Beta)
    with users in multiple roles for RBAC and multi-tenant testing.
    """
    suffix = uuid.uuid4().hex[:6]
    slug_a = f"tenant-alpha-{suffix}"
    slug_b = f"tenant-beta-{suffix}"

    tenant_a = Tenant(slug=slug_a, name="Alpha Clinic", domain_type="healthcare", primary_language="mr")
    tenant_b = Tenant(slug=slug_b, name="Beta Clinic", domain_type="healthcare", primary_language="en")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.commit()
    await db_session.refresh(tenant_a)
    await db_session.refresh(tenant_b)

    # Enable tools on Tenant A
    tool_info = TenantEnabledTool(tenant_id=tenant_a.id, tool_id="clinic.check_service_info", is_enabled=True)
    tool_book = TenantEnabledTool(tenant_id=tenant_a.id, tool_id="clinic.book_appointment", is_enabled=True)
    tool_slots = TenantEnabledTool(tenant_id=tenant_a.id, tool_id="clinic.check_available_slots", is_enabled=True)

    # Enable tools on Tenant B
    tool_info_b = TenantEnabledTool(tenant_id=tenant_b.id, tool_id="clinic.check_service_info", is_enabled=True)
    tool_book_b = TenantEnabledTool(tenant_id=tenant_b.id, tool_id="clinic.book_appointment", is_enabled=True)

    db_session.add_all([tool_info, tool_book, tool_slots, tool_info_b, tool_book_b])

    # Passwords hashed with bcrypt
    test_password = "SecurePassword@123"
    hashed = hash_password(test_password)

    # Users in Tenant A
    user_a_owner = User(
        tenant_id=tenant_a.id,
        email=f"owner@{slug_a}.com",
        full_name="Alpha Owner",
        role="TENANT_OWNER",
        hashed_password=hashed,
        is_active=True,
    )
    user_a_operator = User(
        tenant_id=tenant_a.id,
        email=f"operator@{slug_a}.com",
        full_name="Alpha Operator",
        role="OPERATOR",
        hashed_password=hashed,
        is_active=True,
    )
    user_a_viewer = User(
        tenant_id=tenant_a.id,
        email=f"viewer@{slug_a}.com",
        full_name="Alpha Viewer",
        role="VIEWER",
        hashed_password=hashed,
        is_active=True,
    )
    user_a_inactive = User(
        tenant_id=tenant_a.id,
        email=f"inactive@{slug_a}.com",
        full_name="Alpha Inactive",
        role="OPERATOR",
        hashed_password=hashed,
        is_active=False,
    )

    # User in Tenant B
    user_b_operator = User(
        tenant_id=tenant_b.id,
        email=f"operator@{slug_b}.com",
        full_name="Beta Operator",
        role="OPERATOR",
        hashed_password=hashed,
        is_active=True,
    )

    # Platform Superadmin
    superadmin = User(
        tenant_id=tenant_a.id,
        email=f"superadmin@{slug_a}.com",
        full_name="Platform Superadmin",
        role="PLATFORM_SUPERADMIN",
        hashed_password=hashed,
        is_active=True,
    )

    db_session.add_all([
        user_a_owner,
        user_a_operator,
        user_a_viewer,
        user_a_inactive,
        user_b_operator,
        superadmin,
    ])
    await db_session.commit()
    await db_session.refresh(user_a_owner)
    await db_session.refresh(user_a_operator)
    await db_session.refresh(user_a_viewer)
    await db_session.refresh(user_a_inactive)
    await db_session.refresh(user_b_operator)
    await db_session.refresh(superadmin)

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a_owner": user_a_owner,
        "user_a_operator": user_a_operator,
        "user_a_viewer": user_a_viewer,
        "user_a_inactive": user_a_inactive,
        "user_b_operator": user_b_operator,
        "superadmin": superadmin,
        "raw_password": test_password,
    }


# =========================================================================
# 1. PASSWORD SECURITY & HASHING
# =========================================================================

def test_01_password_hashing():
    raw = "MySecretPass@2026"
    hashed = hash_password(raw)
    assert hashed != raw
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


# =========================================================================
# 2. LOGIN ENDPOINT
# =========================================================================

@pytest.mark.asyncio
async def test_02_login_success(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    user_operator = data["user_a_operator"]
    password = data["raw_password"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": tenant_a.slug,
                "identifier": user_operator.email,
                "password": password,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 15 * 60
        assert "user" in body
        user_info = body["user"]
        assert user_info["id"] == str(user_operator.id)
        assert user_info["tenant_id"] == str(tenant_a.id)
        assert user_info["tenant_slug"] == tenant_a.slug
        assert user_info["role"] == "OPERATOR"
        # Ensure password hash is NOT returned
        assert "hashed_password" not in user_info
        assert "password" not in user_info


@pytest.mark.asyncio
async def test_03_login_failure_wrong_password(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    user_operator = data["user_a_operator"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": tenant_a.slug,
                "identifier": user_operator.email,
                "password": "WrongPassword123",
            },
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid tenant, user identifier, or password"


@pytest.mark.asyncio
async def test_04_login_failure_wrong_tenant(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_b = data["tenant_b"]
    user_a_operator = data["user_a_operator"]
    password = data["raw_password"]

    # User A attempting to log in under Tenant B's slug
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": tenant_b.slug,
                "identifier": user_a_operator.email,
                "password": password,
            },
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "Invalid tenant, user identifier, or password"


@pytest.mark.asyncio
async def test_05_login_failure_inactive_user(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    inactive_user = data["user_a_inactive"]
    password = data["raw_password"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": tenant_a.slug,
                "identifier": inactive_user.email,
                "password": password,
            },
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "User account is disabled"


# =========================================================================
# 3. JWT TOKEN VALIDATION & TAMPERING
# =========================================================================

def test_06_jwt_token_validation_and_tampering():
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    token = create_access_token(user_id=uid, tenant_id=tid, tenant_slug="test-slug", role="OPERATOR", expires_delta_minutes=15)
    payload = decode_access_token(token)
    assert payload["sub"] == str(uid)
    assert payload["tenant_id"] == str(tid)
    assert payload["role"] == "OPERATOR"
    assert payload["token_type"] == "access"

    # Expired token
    expired_token = create_access_token(user_id=uid, tenant_id=tid, tenant_slug="test-slug", role="OPERATOR", expires_delta_minutes=-5)
    with pytest.raises(HTTPException) as exc1:
        decode_access_token(expired_token)
    assert exc1.value.status_code == 401
    assert "expired" in exc1.value.detail.lower()

    # Tampered signature
    tampered_token = token[:-5] + "abcde"
    with pytest.raises(HTTPException) as exc2:
        decode_access_token(tampered_token)
    assert exc2.value.status_code == 401


# =========================================================================
# 4. RBAC & ROLE PERMISSION MAPPING
# =========================================================================

def test_07_rbac_role_permissions_mapping():
    assert "actions.execute" in ROLE_PERMISSIONS_MAP["OPERATOR"]
    assert "actions.confirm" in ROLE_PERMISSIONS_MAP["OPERATOR"]
    assert "actions.reject" in ROLE_PERMISSIONS_MAP["OPERATOR"]
    assert "appointments.read" in ROLE_PERMISSIONS_MAP["OPERATOR"]
    assert "actions.execute" not in ROLE_PERMISSIONS_MAP["VIEWER"]
    assert "appointments.read" in ROLE_PERMISSIONS_MAP["VIEWER"]
    assert "tenant.manage" in ROLE_PERMISSIONS_MAP["TENANT_OWNER"]
    assert "admin.dashboard" in ROLE_PERMISSIONS_MAP["PLATFORM_SUPERADMIN"]


@pytest.mark.asyncio
async def test_08_rbac_viewer_blocked_from_execution(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    viewer = data["user_a_viewer"]

    token = create_access_token(
        user_id=viewer.id,
        tenant_id=tenant_a.id,
        tenant_slug=tenant_a.slug,
        role="VIEWER",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Viewer attempting to propose action
        res = await client.post(
            "/api/v1/actions/propose",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "tool_id": "clinic.check_service_info",
                "intent": "QUERY_SERVICE",
                "parameters": {"service_name": "cleaning"},
            },
        )
        assert res.status_code == 403
        assert "Permission denied" in res.json()["detail"]


@pytest.mark.asyncio
async def test_09_rbac_operator_allowed_execution(setup_test_tenants_and_users, db_session):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    operator = data["user_a_operator"]

    token = create_access_token(
        user_id=operator.id,
        tenant_id=tenant_a.id,
        tenant_slug=tenant_a.slug,
        role="OPERATOR",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/actions/propose",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "tool_id": "clinic.check_service_info",
                "intent": "QUERY_SERVICE",
                "parameters": {"service_name": "cleaning"},
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "SUCCESS"
        assert body["tool_id"] == "clinic.check_service_info"

        # Cleanup execution row
        exec_id = body["execution_id"]
        row = await db_session.get(ActionExecution, uuid.UUID(exec_id))
        if row:
            await db_session.delete(row)
            await db_session.commit()


# =========================================================================
# 5. TENANT ISOLATION
# =========================================================================

@pytest.mark.asyncio
async def test_10_tenant_isolation_cross_tenant_access_blocked(setup_test_tenants_and_users, db_session):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    tenant_b = data["tenant_b"]
    operator_b = data["user_b_operator"]

    # Stage an action under Tenant A
    exec_a = ActionExecution(
        tenant_id=tenant_a.id,
        tool_id="clinic.book_appointment",
        intent_detected="BOOK_APPOINTMENT",
        risk_level=RiskLevel.NORMAL_WRITE.value,
        status=ActionStatus.PENDING_CONFIRMATION.value,
        extracted_parameters={"patient_name": "Patient A", "phone": "9999999999", "date": "2026-10-20", "time_slot": "10:00 AM", "service": "cleaning"},
        sanitized_parameters={"patient_name": "Patient A", "phone": "9999999999", "date": "2026-10-20", "time_slot": "10:00 AM", "service": "cleaning"},
    )
    db_session.add(exec_a)
    await db_session.commit()
    await db_session.refresh(exec_a)

    # Token for Tenant B operator
    token_b = create_access_token(
        user_id=operator_b.id,
        tenant_id=tenant_b.id,
        tenant_slug=tenant_b.slug,
        role="OPERATOR",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant B operator tries to confirm Tenant A's execution
        res = await client.post(
            f"/api/v1/actions/{exec_a.id}/confirm",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail["code"] == "TENANT_ISOLATION_VIOLATION"

    # Cleanup
    await db_session.delete(exec_a)
    await db_session.commit()


# =========================================================================
# 6. ACTION ENDPOINTS REQUIRE AUTHENTICATION
# =========================================================================

@pytest.mark.asyncio
async def test_11_action_endpoints_unauthenticated_blocked():
    transport = ASGITransport(app=app)
    dummy_id = uuid.uuid4()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Propose without token
        res_prop = await client.post(
            "/api/v1/actions/propose",
            json={"tool_id": "clinic.check_service_info", "intent": "QUERY_SERVICE", "parameters": {}},
        )
        assert res_prop.status_code == 401

        # 2. Confirm without token
        res_conf = await client.post(f"/api/v1/actions/{dummy_id}/confirm")
        assert res_conf.status_code == 401

        # 3. Reject without token
        res_rej = await client.post(f"/api/v1/actions/{dummy_id}/reject")
        assert res_rej.status_code == 401


@pytest.mark.asyncio
async def test_12_action_endpoints_authenticated_lifecycle(setup_test_tenants_and_users, db_session):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    operator_a = data["user_a_operator"]

    token_a = create_access_token(
        user_id=operator_a.id,
        tenant_id=tenant_a.id,
        tenant_slug=tenant_a.slug,
        role="OPERATOR",
    )
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Propose Risk 2 booking action -> PENDING_CONFIRMATION
        prop_res = await client.post(
            "/api/v1/actions/propose",
            headers=headers,
            json={
                "tool_id": "clinic.book_appointment",
                "intent": "BOOK_APPOINTMENT",
                "parameters": {
                    "patient_name": "सचिन तेंडुलकर",
                    "phone": "9820011223",
                    "date": "2026-10-25",
                    "time_slot": "04:00 PM",
                    "service": "रूट कॅनाल",
                },
            },
        )
        assert prop_res.status_code == 200
        prop_data = prop_res.json()
        assert prop_data["status"] == "PENDING_CONFIRMATION"
        assert prop_data["requires_confirmation"] is True
        exec_id = prop_data["execution_id"]

        # Step 2: Confirm the action -> SUCCESS
        conf_res = await client.post(f"/api/v1/actions/{exec_id}/confirm", headers=headers)
        assert conf_res.status_code == 200
        conf_data = conf_res.json()
        assert conf_data["status"] == "SUCCESS"
        assert "Confirmed action" in conf_data["message"]
        assert "सचिन तेंडुलकर" in str(conf_data["result"])

        # Step 3: Propose another action and reject it
        prop_res2 = await client.post(
            "/api/v1/actions/propose",
            headers=headers,
            json={
                "tool_id": "clinic.book_appointment",
                "intent": "BOOK_APPOINTMENT",
                "parameters": {
                    "patient_name": "विराट कोहली",
                    "phone": "9820099887",
                    "date": "2026-10-26",
                    "time_slot": "05:00 PM",
                    "service": "क्लिनिंग",
                },
            },
        )
        exec_id2 = prop_res2.json()["execution_id"]

        rej_res = await client.post(f"/api/v1/actions/{exec_id2}/reject", headers=headers)
        assert rej_res.status_code == 200
        assert rej_res.json()["status"] == "REJECTED"

        # Cleanup
        for eid in [exec_id, exec_id2]:
            row = await db_session.get(ActionExecution, uuid.UUID(eid))
            if row:
                await db_session.delete(row)
        await db_session.commit()


# =========================================================================
# 7. ADMIN APPOINTMENTS SECURITY
# =========================================================================

@pytest.mark.asyncio
async def test_13_appointments_get_requires_auth_and_is_tenant_scoped(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    operator_a = data["user_a_operator"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated request -> 401
        unauth = await client.get("/api/appointments")
        assert unauth.status_code == 401

        # Authenticated request -> 200 with tenant_id matching
        token_a = create_access_token(
            user_id=operator_a.id,
            tenant_id=tenant_a.id,
            tenant_slug=tenant_a.slug,
            role="OPERATOR",
        )
        auth_res = await client.get("/api/appointments", headers={"Authorization": f"Bearer {token_a}"})
        assert auth_res.status_code == 200
        body = auth_res.json()
        assert body["status"] == "success"
        assert body["tenant_id"] == str(tenant_a.id)
        assert "appointments" in body


@pytest.mark.asyncio
async def test_14_appointments_delete_bulk_restricted(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    operator_a = data["user_a_operator"]
    superadmin = data["superadmin"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Non-superadmin operator attempts bulk delete -> 403
        op_token = create_access_token(
            user_id=operator_a.id,
            tenant_id=tenant_a.id,
            tenant_slug=tenant_a.slug,
            role="OPERATOR",
        )
        res_op = await client.delete("/api/appointments", headers={"Authorization": f"Bearer {op_token}"})
        assert res_op.status_code == 403

        # Superadmin allowed in development mode
        sa_token = create_access_token(
            user_id=superadmin.id,
            tenant_id=tenant_a.id,
            tenant_slug=tenant_a.slug,
            role="PLATFORM_SUPERADMIN",
        )
        res_sa = await client.delete("/api/appointments", headers={"Authorization": f"Bearer {sa_token}"})
        assert res_sa.status_code == 200
        assert res_sa.json()["status"] == "success"


# =========================================================================
# 8. WEBSOCKET SESSION TICKETS
# =========================================================================

@pytest.mark.asyncio
async def test_15_public_widget_ticket_issuance(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/widget/session", json={"tenant_slug": tenant_a.slug, "language": "mr"})
        assert res.status_code == 200
        body = res.json()
        assert "ticket" in body
        assert "session_id" in body
        assert body["expires_in"] == 300
        assert body["session_type"] == "public"

        # Decode ticket
        ticket_payload = decode_websocket_ticket(body["ticket"])
        assert ticket_payload["session_id"] == body["session_id"]
        assert ticket_payload["tenant_id"] == str(tenant_a.id)
        assert ticket_payload["session_type"] == "public"
        assert ticket_payload["user_id"] is None  # Public sessions have no staff user
        assert set(ticket_payload["allowed_tools"]) == PUBLIC_WIDGET_ALLOWED_TOOLS


@pytest.mark.asyncio
async def test_16_internal_voice_session_ticket_issuance(setup_test_tenants_and_users):
    data = setup_test_tenants_and_users
    tenant_a = data["tenant_a"]
    operator_a = data["user_a_operator"]

    token_a = create_access_token(
        user_id=operator_a.id,
        tenant_id=tenant_a.id,
        tenant_slug=tenant_a.slug,
        role="OPERATOR",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without auth -> 401
        unauth_res = await client.post("/api/v1/voice/session", json={})
        assert unauth_res.status_code == 401

        # With operator auth -> 200
        auth_res = await client.post("/api/v1/voice/session", headers={"Authorization": f"Bearer {token_a}"}, json={})
        assert auth_res.status_code == 200
        body = auth_res.json()
        assert "ticket" in body
        assert body["session_type"] == "internal"

        # Decode ticket
        payload = decode_websocket_ticket(body["ticket"])
        assert payload["user_id"] == str(operator_a.id)
        assert payload["tenant_id"] == str(tenant_a.id)
        assert payload["role"] == "OPERATOR"


# =========================================================================
# 9. WEBSOCKET HANDSHAKE SECURITY & TICKET VALIDATION
# =========================================================================

def test_17_websocket_missing_ticket_rejected():
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/copilot/sess_test_123"):
            pass
    assert exc.value.code == 4401


def test_18_websocket_tampered_ticket_rejected():
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/copilot/sess_test_123?ticket=invalid.tampered.ticket"):
            pass
    assert exc.value.code == 4401


def test_19_websocket_expired_ticket_rejected():
    sess_id = f"sess_{uuid.uuid4().hex[:8]}"
    tid = uuid.uuid4()
    expired_ticket = create_websocket_ticket(
        session_id=sess_id,
        tenant_id=tid,
        tenant_slug="sai-smile",
        session_type="public",
        expires_seconds=-10,
    )
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/copilot/{sess_id}?ticket={expired_ticket}"):
            pass
    assert exc.value.code == 4401


def test_20_websocket_mismatched_session_id_rejected():
    sess_id_ticket = f"sess_{uuid.uuid4().hex[:8]}"
    sess_id_path = f"sess_other_{uuid.uuid4().hex[:8]}"
    tid = uuid.uuid4()
    ticket = create_websocket_ticket(
        session_id=sess_id_ticket,
        tenant_id=tid,
        tenant_slug="sai-smile",
        session_type="public",
        expires_seconds=300,
    )
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/copilot/{sess_id_path}?ticket={ticket}"):
            pass
    assert exc.value.code == 4401


def test_21_websocket_valid_ticket_accepts_connection():
    sess_id = f"sess_{uuid.uuid4().hex[:8]}"
    tid = uuid.uuid4()
    ticket = create_websocket_ticket(
        session_id=sess_id,
        tenant_id=tid,
        tenant_slug="sai-smile",
        session_type="public",
        expires_seconds=300,
        allowed_tools=list(PUBLIC_WIDGET_ALLOWED_TOOLS),
    )
    client = TestClient(app)
    with client.websocket_connect(f"/ws/copilot/{sess_id}?ticket={ticket}") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection_ack"
        assert ack["session_id"] == sess_id


def test_22_websocket_unauthorized_origin_rejected():
    sess_id = f"sess_{uuid.uuid4().hex[:8]}"
    tid = uuid.uuid4()
    ticket = create_websocket_ticket(
        session_id=sess_id,
        tenant_id=tid,
        tenant_slug="sai-smile",
        session_type="public",
        expires_seconds=300,
    )
    client = TestClient(app)
    # Origin from unauthorized malicious domain
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/ws/copilot/{sess_id}?ticket={ticket}",
            headers={"origin": "http://evil-phishing-site.com"},
        ):
            pass
    assert exc.value.code == 4003


def test_23_websocket_configured_origin_accepted():
    sess_id = f"sess_{uuid.uuid4().hex[:8]}"
    tid = uuid.uuid4()
    ticket = create_websocket_ticket(
        session_id=sess_id,
        tenant_id=tid,
        tenant_slug="sai-smile",
        session_type="public",
        expires_seconds=300,
    )
    client = TestClient(app)
    # Origin from configured local frontend
    with client.websocket_connect(
        f"/ws/copilot/{sess_id}?ticket={ticket}",
        headers={"origin": "http://localhost:3000"},
    ) as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection_ack"


# =========================================================================
# 10. CORS CONFIGURATION
# =========================================================================

@pytest.mark.asyncio
async def test_24_cors_configured_origins():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight from configured origin
        res_ok = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert res_ok.status_code == 200
        assert res_ok.headers.get("access-control-allow-origin") == "http://localhost:3000"

        # Preflight from unapproved origin
        res_bad = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://attacker.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        # Should not grant allow-origin to attacker
        assert res_bad.headers.get("access-control-allow-origin") != "http://attacker.com"
