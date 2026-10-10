import inspect
import logging
from typing import Any, Dict, List, Optional

from app.adapters.base import BaseDomainAdapter, ToolManifest
# Zero-regression delegation bridge to existing functional clinic tools
from agent.tools import check_service_info, check_available_slots, book_appointment

logger = logging.getLogger("voicedesk.adapters.healthcare")


class HealthcareAdapter(BaseDomainAdapter):
    """
    Domain Adapter #1: Healthcare & Dental Clinic Copilot.
    Wraps existing clinic tools as standard VoiceDesk AI business actions.
    """

    @property
    def domain_key(self) -> str:
        return "healthcare"

    def get_supported_tools(self) -> List[ToolManifest]:
        return [
            ToolManifest(
                name="clinic.check_service_info",
                description="Checks pricing, treatment duration, specialist doctor, and description for clinic dental services.",
                risk_level=1,
                requires_confirmation=False,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Treatment or service keyword (e.g. cleaning, root canal, checkup, whitening, extraction, invisalign)",
                        }
                    },
                    "required": ["service_name"],
                },
                required_permissions=["VIEWER", "OPERATOR", "MANAGER", "TENANT_OWNER"],
            ),
            ToolManifest(
                name="clinic.check_available_slots",
                description="Retrieves available doctor consultation appointment times for a given date.",
                risk_level=1,
                requires_confirmation=False,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "Requested date or relative day (e.g. 'tomorrow', 'Friday', '2026-10-02')",
                        }
                    },
                    "required": ["date"],
                },
                required_permissions=["VIEWER", "OPERATOR", "MANAGER", "TENANT_OWNER"],
            ),
            ToolManifest(
                name="clinic.book_appointment",
                description="Books and confirms an official dental appointment for a patient, saving it to clinic records.",
                risk_level=2,
                requires_confirmation=True,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "patient_name": {"type": "string", "description": "Full name of the patient"},
                        "phone": {"type": "string", "description": "Contact phone number"},
                        "date": {"type": "string", "description": "Date of appointment"},
                        "time_slot": {"type": "string", "description": "Preferred time slot (e.g. '11:00 AM')"},
                        "service": {"type": "string", "description": "Service or treatment requested"},
                    },
                    "required": ["patient_name", "phone", "date", "time_slot", "service"],
                },
                required_permissions=["OPERATOR", "MANAGER", "TENANT_OWNER"],
            ),
        ]

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        logger.info(f"HealthcareAdapter executing tool '{tool_name}' with params: {params}")

        # Normalize tool identifier (supports both 'clinic.book_appointment' and 'book_appointment')
        normalized_name = tool_name.replace("clinic.", "")

        if normalized_name == "check_service_info":
            service_name = params.get("service_name", "")
            return check_service_info.invoke({"service_name": service_name})

        elif normalized_name == "check_available_slots":
            date_arg = params.get("date", "today")
            return check_available_slots.invoke({"date": date_arg})

        elif normalized_name == "book_appointment":
            return book_appointment.invoke({
                "patient_name": params.get("patient_name", ""),
                "phone": params.get("phone", ""),
                "date": params.get("date", ""),
                "time_slot": params.get("time_slot", ""),
                "service": params.get("service", ""),
            })

        else:
            raise ValueError(f"Tool '{tool_name}' is not supported by HealthcareAdapter")
