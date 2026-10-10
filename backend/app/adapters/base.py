from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolManifest(BaseModel):
    """
    Standard definition and capability manifest for an adapter-exposed action/tool.
    """
    name: str = Field(..., description="Unique tool identifier, e.g. clinic.check_service_info")
    description: str = Field(..., description="Human and LLM-readable description of what this action does")
    risk_level: int = Field(default=1, description="1=READ, 2=NORMAL_WRITE, 3=CRITICAL")
    requires_confirmation: bool = Field(default=False, description="Whether explicit caller confirmation is required before execution")
    parameters_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON schema defining expected input parameters")
    required_permissions: List[str] = Field(default_factory=list, description="Roles/permissions required to execute this tool")


class BaseDomainAdapter(ABC):
    """
    Domain-neutral interface for all business domain adapters.
    Examples: HealthcareAdapter (Domain #1), VyaparProAdapter, DairyAdapter, SalonAdapter.
    """

    @property
    @abstractmethod
    def domain_key(self) -> str:
        """Domain key, e.g. 'healthcare', 'retail', 'restaurant'."""
        pass

    @abstractmethod
    def get_supported_tools(self) -> List[ToolManifest]:
        """
        Returns list of ToolManifest objects describing tools supported by this adapter.
        """
        pass

    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Safely executes the requested tool action with provided parameters and context.
        """
        pass
