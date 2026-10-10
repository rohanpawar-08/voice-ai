import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseDomainAdapter, ToolManifest
from app.adapters.healthcare import HealthcareAdapter
from app.models.platform import TenantEnabledTool, ToolDefinition
from app.engine.schemas import (
    ClinicServiceInfoParams,
    ClinicAvailableSlotsParams,
    ClinicBookAppointmentParams,
)
from app.engine.exceptions import (
    UnknownToolError,
    ToolDisabledError,
    PermissionDeniedError,
)

logger = logging.getLogger("voicedesk.engine.registry")


class ToolRegistry:
    """
    Deterministic Tool Registry.
    Knows trusted registered domain adapters, resolves tools,
    and validates tenant enablement without magic global singletons.
    """

    def __init__(self):
        self._adapters: Dict[str, BaseDomainAdapter] = {}
        self._tool_to_domain: Dict[str, str] = {}
        self._tool_manifests: Dict[str, ToolManifest] = {}
        self._param_models: Dict[str, Type[BaseModel]] = {
            "clinic.check_service_info": ClinicServiceInfoParams,
            "clinic.check_available_slots": ClinicAvailableSlotsParams,
            "clinic.book_appointment": ClinicBookAppointmentParams,
        }

    def register_adapter(self, adapter: BaseDomainAdapter) -> None:
        """Registers a domain adapter and indexes its tools."""
        domain = adapter.domain_key
        self._adapters[domain] = adapter
        for manifest in adapter.get_supported_tools():
            self._tool_to_domain[manifest.name] = domain
            self._tool_manifests[manifest.name] = manifest

    def register_param_model(self, tool_id: str, model_cls: Type[BaseModel]) -> None:
        """Registers a concrete parameter validation model for a tool."""
        self._param_models[tool_id] = model_cls

    def resolve_tool(self, tool_id: str) -> Tuple[BaseDomainAdapter, ToolManifest]:
        """
        Resolves trusted adapter and ToolManifest for a tool_id.
        Raises UnknownToolError if tool is not registered.
        """
        if tool_id not in self._tool_manifests:
            raise UnknownToolError(f"Tool '{tool_id}' is unknown or not registered.")
        domain = self._tool_to_domain[tool_id]
        adapter = self._adapters[domain]
        manifest = self._tool_manifests[tool_id]
        return adapter, manifest

    def get_parameter_model(self, tool_id: str) -> Optional[Type[BaseModel]]:
        return self._param_models.get(tool_id)

    async def verify_tenant_tool_enablement(
        self,
        tenant_id: uuid.UUID,
        tool_id: str,
        db: AsyncSession,
        caller_role: Optional[str] = None,
    ) -> TenantEnabledTool:
        """
        Verifies that the tenant has enabled this tool in the database.
        Raises ToolDisabledError if disabled, or PermissionDeniedError if role insufficient.
        """
        # 1. Resolve tool first to ensure it's registered
        _, manifest = self.resolve_tool(tool_id)

        # 2. Check tenant enablement in DB
        stmt = select(TenantEnabledTool).where(
            TenantEnabledTool.tenant_id == tenant_id,
            TenantEnabledTool.tool_id == tool_id,
        )
        res = await db.execute(stmt)
        mapping = res.scalar_one_or_none()

        if mapping is None:
            raise ToolDisabledError(f"Tool '{tool_id}' is not assigned to tenant {tenant_id}.")

        if not mapping.is_enabled:
            raise ToolDisabledError(f"Tool '{tool_id}' is disabled for tenant {tenant_id}.")

        # 3. Check manifest required permissions against caller role if specified
        if manifest.required_permissions and caller_role:
            if caller_role not in manifest.required_permissions:
                raise PermissionDeniedError(
                    f"Caller role '{caller_role}' lacks permission for tool '{tool_id}'. "
                    f"Required: {manifest.required_permissions}"
                )

        return mapping


def get_default_registry() -> ToolRegistry:
    """Factory creating registry with default domain adapters."""
    registry = ToolRegistry()
    registry.register_adapter(HealthcareAdapter())
    return registry
