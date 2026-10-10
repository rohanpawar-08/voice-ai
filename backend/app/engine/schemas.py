import enum
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class ActionStatusEnum(str, enum.Enum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class ActionRequest(BaseModel):
    """
    Strongly typed action proposal schema.
    The LLM or client proposes this structured action.
    """
    tool_id: str = Field(..., description="Target tool ID, e.g. clinic.book_appointment")
    intent: str = Field(..., description="Action intent detected, e.g. BOOK_APPOINTMENT")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extracted parameters dictionary")
    idempotency_key: Optional[str] = Field(default=None, description="Optional idempotency key for safe retries")
    confirmed: bool = Field(default=False, description="Whether caller explicitly provided confirmation")

    @field_validator("tool_id", "intent")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class ActionResult(BaseModel):
    """
    Deterministic action result returned to client / agent.
    """
    execution_id: uuid.UUID = Field(..., description="ActionExecution record UUID")
    status: ActionStatusEnum = Field(..., description="Action status")
    tool_id: str = Field(..., description="Target tool ID")
    message: str = Field(..., description="Human/voice readable feedback message")
    requires_confirmation: bool = Field(default=False, description="Whether caller confirmation is needed")
    confirmation_prompt: Optional[str] = Field(default=None, description="Deterministic confirmation prompt")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Execution return data if successful")
    error_code: Optional[str] = Field(default=None, description="Deterministic error code if failed/rejected")


# Parameter validation schemas for supported tools
class ClinicServiceInfoParams(BaseModel):
    service_name: str = Field(..., min_length=1, description="Treatment or service name")

    @field_validator("service_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("service_name must not be empty")
        return s


class ClinicAvailableSlotsParams(BaseModel):
    date: str = Field(default="today", description="Requested date or relative day")

    @field_validator("date")
    @classmethod
    def clean_date(cls, v: str) -> str:
        s = v.strip()
        return s if s else "today"


class ClinicBookAppointmentParams(BaseModel):
    patient_name: str = Field(..., min_length=2, description="Patient full name")
    phone: str = Field(..., min_length=5, description="Contact phone number")
    date: str = Field(..., min_length=2, description="Appointment date")
    time_slot: str = Field(..., min_length=2, description="Time slot")
    service: str = Field(..., min_length=2, description="Service requested")

    @field_validator("patient_name", "phone", "date", "time_slot", "service")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Required appointment field cannot be empty")
        return s
