from typing import Optional, Dict, Any


class ActionEngineError(Exception):
    """Base exception for deterministic action engine failures."""
    code: str = "ACTION_ENGINE_ERROR"

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class UnknownToolError(ActionEngineError):
    code = "UNKNOWN_TOOL"


class ToolDisabledError(ActionEngineError):
    code = "TOOL_DISABLED"


class InvalidParametersError(ActionEngineError):
    code = "INVALID_PARAMETERS"


class TenantNotFoundError(ActionEngineError):
    code = "TENANT_NOT_FOUND"


class PermissionDeniedError(ActionEngineError):
    code = "PERMISSION_DENIED"


class ConfirmationRequiredError(ActionEngineError):
    code = "CONFIRMATION_REQUIRED"


class CriticalActionBlockedError(ActionEngineError):
    code = "CRITICAL_ACTION_BLOCKED"


class DuplicateActionError(ActionEngineError):
    code = "DUPLICATE_ACTION"


class ExecutionFailedError(ActionEngineError):
    code = "EXECUTION_FAILED"


class InvalidStateTransitionError(ActionEngineError):
    code = "INVALID_STATE_TRANSITION"


class TenantIsolationError(ActionEngineError):
    code = "TENANT_ISOLATION_VIOLATION"


class ActionNotFoundError(ActionEngineError):
    code = "ACTION_NOT_FOUND"
