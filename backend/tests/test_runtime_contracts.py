"""Focused contracts for the authority-ready runtime primitives."""

import pytest

from app.core.exceptions import DomainError
from app.domain.entities import ConsultationCase
from app.observability.audit import AuditLog
from app.repositories.workflow import MemoryWorkflowRecordStore
from app.runtime import EventBus, HookRunner, RecoveryDecision, RecoveryPolicy, RuntimeContext
from app.runtime.checkpoints import CheckpointStore, ExecutionCheckpoint
from app.runtime.failures import FailureCategory, FailureInfo


def test_runtime_context_is_immutable_and_metadata_is_read_only():
    context = RuntimeContext(
        case_id="case-1",
        tenant_id="tenant-a",
        user_id="user-a",
        trace_id="trace-1",
        provider_metadata={"provider": "fixture"},
    )
    with pytest.raises(TypeError):
        context.provider_metadata["provider"] = "other"
    with pytest.raises(AttributeError):
        context.status = "failed"


def test_event_bus_sanitizes_payload_and_isolates_subscribers():
    seen = []
    bus = EventBus()
    bus.subscribe(lambda event: (_ for _ in ()).throw(RuntimeError("observer")))
    bus.subscribe(seen.append)
    context = RuntimeContext("case-1", "tenant-a", "user-a", "trace-1")
    from app.runtime.events import RuntimeEvent
    bus.publish(RuntimeEvent.from_context(context, "consultation.started", payload={"question": "secret", "count": 2}))
    assert seen[0].payload == {"question": "[redacted]", "count": 2}


def test_hook_runner_isolates_hook_failure():
    class Broken:
        def before_run(self, _context):
            raise RuntimeError("broken")

    diagnostics = None
    runner = HookRunner((Broken(),))
    runner.before_run(RuntimeContext("case-1", "tenant-a", "user-a", "trace-1"))
    assert runner.diagnostics.failures == [{"hook": "before_run", "type": "RuntimeError"}]


def test_recovery_policy_requires_idempotency_and_authorized_fallback():
    failure = FailureInfo("PROVIDER_TIMEOUT", FailureCategory.PROVIDER_TIMEOUT, "provider", True, True, "retry", "TimeoutError", 1, "trace-1", "TimeoutError")
    policy = RecoveryPolicy()
    assert policy.decide(failure) == RecoveryDecision.FAIL_CLOSED
    assert policy.decide(failure, idempotent=True) == RecoveryDecision.RETRY
    assert policy.decide(failure, fallback_name="keyword", authorization_compatible=True) == RecoveryDecision.FAIL_CLOSED


def test_checkpoint_store_validates_scope_and_uses_workflow_version():
    records = MemoryWorkflowRecordStore()
    store = CheckpointStore(records)
    checkpoint = ExecutionCheckpoint("case-1", "tenant-a", "trace-1", 1, "retrieve", "executing", can_resume=True)
    saved = store.save(checkpoint)
    assert saved.case_id == "case-1"
    with pytest.raises(DomainError, match="does not match"):
        store.load(case_id="case-1", tenant_id="tenant-a", trace_id="trace-other", case_version=1)
    with pytest.raises(DomainError, match="stale"):
        records.put("execution_checkpoint", "case-1", "tenant-a", checkpoint.as_dict(), expected_version=0)


def test_audit_redacts_sensitive_payload_and_empty_chain_is_invalid():
    audit = AuditLog()
    assert audit.verify("missing", "tenant-a") is False
    audit.append(case_id="case-1", tenant_id="tenant-a", event_type="consultation.created", actor="user-a", payload={"question": "private", "answer": "private", "status": "received"})
    event = audit.list("case-1", "tenant-a")[0]
    assert event.payload["question"] == "[redacted]"
    assert event.payload["status"] == "received"
    assert audit.verify("case-1", "tenant-a") is True


def test_workflow_store_rejects_stale_versions():
    records = MemoryWorkflowRecordStore()
    first = records.put("profile", "user-a", "tenant-a", {"risk_level": "low"})
    second = records.put("profile", "user-a", "tenant-a", {"risk_level": "medium"}, expected_version=first["version"])
    assert second["version"] == 2
    with pytest.raises(DomainError, match="stale"):
        records.put("profile", "user-a", "tenant-a", {"risk_level": "high"}, expected_version=first["version"])
