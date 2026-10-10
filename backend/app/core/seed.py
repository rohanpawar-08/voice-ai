import asyncio
import logging
import uuid
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.platform import (
    Tenant,
    User,
    ToolDefinition,
    TenantEnabledTool,
    DomainType,
    UserRole,
    RiskLevel,
)
from app.adapters.healthcare import HealthcareAdapter
from app.core.security import hash_password
from config import settings

logger = logging.getLogger("voicedesk.seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Deterministic UUID for Tenant 1 (Sai Smile Dental Clinic) to guarantee idempotency across environments
SAI_SMILE_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAI_SMILE_USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


async def seed_initial_data() -> Dict[str, Any]:
    """
    Idempotent development seed mechanism for VoiceDesk AI.
    Seeds Tenant 1 (साई स्माईल / Sai Smile Dental Clinic), admin user,
    supported tool definitions, and tenant tool enablements.
    """
    logger.info("Starting idempotent database seed for VoiceDesk AI...")

    results = {
        "tenant": None,
        "user": None,
        "tools_created": 0,
        "tools_enabled": 0,
    }

    async with AsyncSessionLocal() as session:
        try:
            # 1. Seed Tenant 1 (Sai Smile Dental Clinic)
            stmt = select(Tenant).where(Tenant.slug == "sai-smile")
            res = await session.execute(stmt)
            tenant = res.scalar_one_or_none()

            if tenant is None:
                tenant = Tenant(
                    id=SAI_SMILE_TENANT_ID,
                    slug="sai-smile",
                    name="साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental Clinic)",
                    domain_type=DomainType.HEALTHCARE.value,
                    timezone="Asia/Kolkata",
                    primary_language="mr",
                    is_active=True,
                )
                session.add(tenant)
                await session.flush()
                logger.info(f"Created Tenant: {tenant.name} ({tenant.slug})")
            else:
                logger.info(f"Tenant already exists: {tenant.name} ({tenant.slug})")
            results["tenant"] = str(tenant.id)

            # 2. Seed Default Owner User for Tenant 1
            stmt = select(User).where(User.tenant_id == tenant.id, User.email == "admin@saismile.com")
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            pwd_hash = hash_password(settings.DEV_SEED_ADMIN_PASSWORD)

            if user is None:
                user = User(
                    id=SAI_SMILE_USER_ID,
                    tenant_id=tenant.id,
                    email="admin@saismile.com",
                    phone="+91 98220 12345",
                    full_name="डॉ. स्नेहा पाटील (Dr. Sneha Patil - Clinic Director)",
                    role=UserRole.TENANT_OWNER.value,
                    hashed_password=pwd_hash,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                logger.info(f"Created User: {user.full_name} ({user.role})")
            else:
                user.hashed_password = pwd_hash
                logger.info(f"User already exists: {user.full_name} ({user.email}), updated password hash")
            results["user"] = str(user.id)

            # 3. Seed Tool Definitions from HealthcareAdapter
            adapter = HealthcareAdapter()
            manifests = adapter.get_supported_tools()

            for manifest in manifests:
                stmt = select(ToolDefinition).where(ToolDefinition.id == manifest.name)
                res = await session.execute(stmt)
                tool_def = res.scalar_one_or_none()

                if tool_def is None:
                    tool_def = ToolDefinition(
                        id=manifest.name,
                        domain_key=adapter.domain_key,
                        name=manifest.name.replace("clinic.", "").replace("_", " ").title(),
                        description=manifest.description,
                        risk_level=manifest.risk_level,
                        requires_confirmation=manifest.requires_confirmation,
                        parameters_schema=manifest.parameters_schema,
                        is_global_active=True,
                    )
                    session.add(tool_def)
                    await session.flush()
                    results["tools_created"] += 1
                    logger.info(f"Created ToolDefinition: {tool_def.id}")
                else:
                    # Update fields if schema evolved
                    tool_def.description = manifest.description
                    tool_def.risk_level = manifest.risk_level
                    tool_def.requires_confirmation = manifest.requires_confirmation
                    tool_def.parameters_schema = manifest.parameters_schema
                    logger.info(f"Updated ToolDefinition: {tool_def.id}")

                # 4. Enable Tool for Tenant 1
                stmt = select(TenantEnabledTool).where(
                    TenantEnabledTool.tenant_id == tenant.id,
                    TenantEnabledTool.tool_id == manifest.name,
                )
                res = await session.execute(stmt)
                enabled_tool = res.scalar_one_or_none()

                if enabled_tool is None:
                    enabled_tool = TenantEnabledTool(
                        tenant_id=tenant.id,
                        tool_id=manifest.name,
                        is_enabled=True,
                        confirmation_policy={"mode": "standard", "require_confirmation": manifest.requires_confirmation},
                    )
                    session.add(enabled_tool)
                    results["tools_enabled"] += 1
                    logger.info(f"Enabled Tool '{manifest.name}' for Tenant '{tenant.slug}'")

            await session.commit()
            logger.info("Database seeding successfully completed.")
            return results

        except Exception as e:
            await session.rollback()
            logger.error(f"Error seeding database: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_initial_data())
