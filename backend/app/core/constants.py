"""跨层共享的状态、风险等级和错误码。"""

from enum import StrEnum


class ConsultationStatus(StrEnum):
    RECEIVED = "received"
    CLASSIFIED = "classified"
    CLARIFICATION_REQUIRED = "clarification_required"
    COMPLIANCE_PRECHECK = "compliance_precheck"
    EXECUTING = "executing"
    HUMAN_REVIEW = "human_review"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLIANCE_POSTCHECK = "compliance_postcheck"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"
    EXPIRED = "expired"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    COMPLIANCE_BLOCKED = "COMPLIANCE_BLOCKED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
