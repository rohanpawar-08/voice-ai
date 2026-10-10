from typing import Any, Dict, Optional, Tuple
from app.adapters.base import ToolManifest
from app.models.platform import RiskLevel
from app.engine.exceptions import CriticalActionBlockedError


class ConfirmationPolicyEngine:
    """
    Central deterministic confirmation policy engine.
    Never delegates safety decisions to the LLM.
    """

    @staticmethod
    def evaluate_policy(
        manifest: ToolManifest,
        tenant_policy: Optional[Dict[str, Any]],
        confirmed_by_caller: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether confirmation is required or action is blocked.

        Returns:
            (requires_confirmation: bool, block_reason: Optional[str])

        Rules:
        - Risk 1 (READ): never requires confirmation.
        - Risk 2 (NORMAL_WRITE): requires confirmation unless confirmed_by_caller == True
          OR tenant explicitly overrides with safe 'never'.
        - Risk 3 (CRITICAL): ALWAYS BLOCKED in V1-02. Tenant 'never' cannot override Risk 3!
        """
        risk = manifest.risk_level

        # Risk 3 is strictly blocked through voice in V1-02
        if risk >= RiskLevel.CRITICAL.value:
            return False, "CRITICAL_ACTION_BLOCKED: Level 3 actions cannot be executed via voice."

        # Risk 1 is read-only: execute immediately
        if risk == RiskLevel.READ.value:
            return False, None

        # Risk 2 (NORMAL_WRITE)
        if confirmed_by_caller:
            # Caller has already confirmed this action
            return False, None

        # Check tenant policy override if present
        mode = "default"
        if tenant_policy and isinstance(tenant_policy, dict):
            mode = tenant_policy.get("mode", "default")
            # If explicit override says 'never'
            if mode == "never":
                return False, None
            if mode == "always":
                return True, None

        # Default for Risk 2 is confirmation required
        return True, None

    @staticmethod
    def generate_confirmation_prompt(
        tool_id: str,
        sanitized_params: Dict[str, Any],
        language: str = "mr",
    ) -> str:
        """
        Deterministic, safe confirmation prompt generator.
        Supports Marathi (mr) and English (en).
        """
        lang = (language or "mr").lower()

        if tool_id == "clinic.book_appointment":
            patient = sanitized_params.get("patient_name", "")
            date = sanitized_params.get("date", "")
            time_slot = sanitized_params.get("time_slot", "")
            service = sanitized_params.get("service", "")

            if lang.startswith("mr"):
                if patient and date and time_slot:
                    return f"{patient} यांच्यासाठी {date} रोजी {time_slot} वाजता {service} अपॉइंटमेंट बुक करायची आहे. खात्री आहे का?"
                return "ही अपॉइंटमेंट बुक करायची आहे. खात्री आहे का?"
            else:
                if patient and date and time_slot:
                    return f"Do you want me to book an appointment for {patient} on {date} at {time_slot} for {service}?"
                return "Do you want me to book this appointment?"

        # Generic fallback
        if lang.startswith("mr"):
            return "हे बदल सेव्ह करायचे आहेत. खात्री आहे का?"
        return "Do you want me to save this change?"
