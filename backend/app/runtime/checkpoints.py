"""Tenant-scoped execution checkpoints kept separate from the audit chain."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from app.core.exceptions import DomainError, NotFoundError

CHECKPOINT_RECORD_TYPE = "execution_checkpoint"
CHECKPOINT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ExecutionCheckpoint:
    case_id: str
    tenant_id: str
    trace_id: str
    case_version: int
    step_id: str
    status: str
    plan_version: str = ""
    input_fingerprint: str = ""
    output_reference: str = ""
    attempt: int = 1
    provider: str = ""
    source_id: str = ""
    pending_action: str = ""
    can_resume: bool = False
    policy_version: str = "1.0.0"
    schema_version: str = CHECKPOINT_SCHEMA_VERSION
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.case_id or not self.tenant_id or not self.trace_id or not self.step_id:
            raise ValueError("checkpoint identifiers and step_id are required")
        if self.case_version < 1 or self.attempt < 1:
            raise ValueError("checkpoint versions and attempts must be positive")
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("unsupported checkpoint schema version")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "trace_id": self.trace_id,
            "case_version": self.case_version,
            "step_id": self.step_id,
            "status": self.status,
            "plan_version": self.plan_version,
            "input_fingerprint": self.input_fingerprint,
            "output_reference": self.output_reference,
            "attempt": self.attempt,
            "provider": self.provider,
            "source_id": self.source_id,
            "pending_action": self.pending_action,
            "can_resume": self.can_resume,
            "policy_version": self.policy_version,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionCheckpoint":
        return cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})


class WorkflowRecordStore(Protocol):
    def find(self, record_type: str, record_id: str, tenant_id: str) -> dict[str, Any] | None: ...
    def put(self, record_type: str, record_id: str, tenant_id: str, payload: dict[str, Any], *, expected_version: int | None = None) -> dict[str, Any]: ...


class CheckpointStore:
    def __init__(self, records: WorkflowRecordStore) -> None:
        self.records = records

    def save(self, checkpoint: ExecutionCheckpoint, *, expected_version: int | None = None) -> ExecutionCheckpoint:
        saved = self.records.put(
            CHECKPOINT_RECORD_TYPE,
            checkpoint.case_id,
            checkpoint.tenant_id,
            checkpoint.as_dict(),
            expected_version=expected_version,
        )
        return ExecutionCheckpoint.from_dict(saved)

    def load(
        self,
        *,
        case_id: str,
        tenant_id: str,
        trace_id: str,
        case_version: int,
        plan_version: str = "",
        input_fingerprint: str = "",
    ) -> ExecutionCheckpoint:
        value = self.records.find(CHECKPOINT_RECORD_TYPE, case_id, tenant_id)
        if value is None:
            raise NotFoundError("execution checkpoint not found")
        checkpoint = ExecutionCheckpoint.from_dict(value)
        if checkpoint.tenant_id != tenant_id or checkpoint.case_id != case_id:
            raise DomainError("CHECKPOINT_INVALID", "checkpoint scope is invalid", 409)
        if checkpoint.trace_id != trace_id or checkpoint.case_version != case_version:
            raise DomainError("CHECKPOINT_STALE", "checkpoint does not match current consultation", 409)
        if plan_version and checkpoint.plan_version != plan_version:
            raise DomainError("CHECKPOINT_INVALID", "checkpoint plan version does not match", 409)
        if input_fingerprint and checkpoint.input_fingerprint != input_fingerprint:
            raise DomainError("CHECKPOINT_INVALID", "checkpoint input does not match", 409)
        if not checkpoint.can_resume:
            raise DomainError("CHECKPOINT_NOT_RESUMABLE", "checkpoint cannot be resumed", 409)
        return checkpoint
