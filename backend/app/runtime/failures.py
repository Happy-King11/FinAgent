"""Structured failures and deliberately conservative recovery decisions."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping
from uuid import uuid4

from app.core.exceptions import DomainError


class FailureCategory(StrEnum):
    INVALID_ARGUMENT = "invalid_argument"
    COMPLIANCE = "compliance"
    AUTHORIZATION = "authorization"
    DATA_QUALITY = "data_quality"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RETRIEVAL = "retrieval"
    CALCULATION = "calculation"
    LLM_CONSTRAINT = "llm_constraint"
    PERSISTENCE = "persistence"
    HUMAN_REVIEW = "human_review"
    INTERNAL = "internal"


class RecoveryDecision(StrEnum):
    FAIL_CLOSED = "fail_closed"
    RETRY = "retry"
    FALLBACK = "fallback"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    NO_ACTION = "no_action"


@dataclass(frozen=True)
class FailureInfo:
    error_code: str
    category: FailureCategory
    source: str
    retryable: bool
    safe_to_fallback: bool
    user_message: str
    internal_message: str
    attempt: int
    trace_id: str
    original_exception_type: str
    step_id: str = ""
    provider_or_component: str = ""
    failure_id: str = field(default_factory=lambda: f"failure_{uuid4().hex}")
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        trace_id: str,
        source: str,
        step_id: str = "",
        attempt: int = 1,
    ) -> "FailureInfo":
        if isinstance(exc, DomainError):
            return cls(
                error_code=exc.code,
                category=_category_for_code(exc.code),
                source=source,
                retryable=False,
                safe_to_fallback=False,
                user_message=exc.message,
                internal_message=type(exc).__name__,
                attempt=attempt,
                trace_id=trace_id,
                original_exception_type=type(exc).__name__,
                step_id=step_id,
            )
        return cls(
            error_code="RUNTIME_EXECUTION_FAILED",
            category=FailureCategory.INTERNAL,
            source=source,
            retryable=False,
            safe_to_fallback=False,
            user_message="当前咨询流程不可用，请稍后重试。",
            internal_message=type(exc).__name__,
            attempt=attempt,
            trace_id=trace_id,
            original_exception_type=type(exc).__name__,
            step_id=step_id,
        )


def _category_for_code(code: str) -> FailureCategory:
    upper = code.upper()
    if "COMPLIANCE" in upper or "BLOCK" in upper:
        return FailureCategory.COMPLIANCE
    if "AUTH" in upper or "ENTITLEMENT" in upper or "TENANT" in upper:
        return FailureCategory.AUTHORIZATION
    if "QUALITY" in upper or "STALE" in upper:
        return FailureCategory.DATA_QUALITY
    if "TIMEOUT" in upper:
        return FailureCategory.PROVIDER_TIMEOUT
    if "RATE" in upper:
        return FailureCategory.PROVIDER_RATE_LIMIT
    if "PROVIDER" in upper or "UNAVAILABLE" in upper:
        return FailureCategory.PROVIDER_UNAVAILABLE
    if "RETRIEVAL" in upper:
        return FailureCategory.RETRIEVAL
    if "CALCULATION" in upper:
        return FailureCategory.CALCULATION
    return FailureCategory.INTERNAL


class RecoveryPolicy:
    """Default to fail-closed; retries/fallbacks require declared safe operations."""

    def decide(
        self,
        failure: FailureInfo,
        *,
        idempotent: bool = False,
        fallback_name: str = "",
        authorization_compatible: bool = False,
    ) -> RecoveryDecision:
        if failure.category in {
            FailureCategory.COMPLIANCE,
            FailureCategory.AUTHORIZATION,
            FailureCategory.DATA_QUALITY,
            FailureCategory.CALCULATION,
            FailureCategory.LLM_CONSTRAINT,
            FailureCategory.PERSISTENCE,
        }:
            return RecoveryDecision.FAIL_CLOSED
        if failure.category == FailureCategory.HUMAN_REVIEW:
            return RecoveryDecision.REQUIRE_HUMAN_REVIEW
        if failure.retryable and idempotent:
            return RecoveryDecision.RETRY
        # A fallback must be both explicitly authorized and safe to repeat.  A
        # non-idempotent operation cannot be recovered by substituting another
        # path because its side effects may already have occurred.
        if failure.safe_to_fallback and idempotent and fallback_name and authorization_compatible:
            return RecoveryDecision.FALLBACK
        return RecoveryDecision.FAIL_CLOSED
