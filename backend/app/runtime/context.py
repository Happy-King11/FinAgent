"""Immutable execution context shared by runtime observers."""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class RuntimeContext:
    """Safe, immutable context; sensitive business payloads stay outside it."""

    case_id: str
    tenant_id: str
    user_id: str
    trace_id: str
    request_id: str = ""
    session_id: str = ""
    workflow_ref: str = ""
    workflow_version: str = ""
    pipeline_ref: str = ""
    pipeline_version: str = ""
    status: str = "received"
    attempt: int = 1
    risk_level: str = "low"
    confirmed: bool = False
    approved: bool = False
    policy_version: str = "1.0.0"
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.case_id or not self.tenant_id or not self.trace_id:
            raise ValueError("case_id, tenant_id and trace_id are required")
        if self.attempt < 1:
            raise ValueError("attempt must be positive")
        object.__setattr__(self, "provider_metadata", MappingProxyType(dict(self.provider_metadata)))
        object.__setattr__(self, "source_metadata", MappingProxyType(dict(self.source_metadata)))

    def with_status(self, status: str) -> "RuntimeContext":
        return RuntimeContext(**{**self.as_dict(), "status": status})

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "workflow_ref": self.workflow_ref,
            "workflow_version": self.workflow_version,
            "pipeline_ref": self.pipeline_ref,
            "pipeline_version": self.pipeline_version,
            "status": self.status,
            "attempt": self.attempt,
            "risk_level": self.risk_level,
            "confirmed": self.confirmed,
            "approved": self.approved,
            "policy_version": self.policy_version,
            "provider_metadata": dict(self.provider_metadata),
            "source_metadata": dict(self.source_metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_case(cls, case: Any, *, request_id: str = "", session_id: str = "") -> "RuntimeContext":
        risk = getattr(case, "risk_level", "low")
        risk = getattr(risk, "value", risk)
        return cls(
            case_id=case.id,
            tenant_id=case.tenant_id,
            user_id=case.user_id,
            trace_id=case.trace_id,
            request_id=request_id,
            session_id=session_id,
            status=getattr(getattr(case, "status", "received"), "value", getattr(case, "status", "received")),
            risk_level=risk,
            confirmed=getattr(case, "confirmed_at", None) is not None,
            created_at=getattr(case, "created_at", None),
        )
