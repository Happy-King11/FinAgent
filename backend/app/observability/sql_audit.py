"""PostgreSQL-backed audit log preserving a serialized per-case hash chain."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.exceptions import DomainError
from app.infrastructure.database.models import AuditEventModel
from app.infrastructure.database.session import set_tenant_context
from app.observability.audit import AuditEvent, _safe_payload


class SQLAuditLog:
    def __init__(self, session_factory, genesis_prefix: str = "financial-agent:audit:genesis"):
        self.session_factory = session_factory
        self.genesis_prefix = genesis_prefix

    def append(self, *, case_id: str, tenant_id: str, event_type: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        created_at = datetime.now(timezone.utc).isoformat()
        safe_payload = _safe_payload(payload)
        try:
            with self.session_factory() as session:
                set_tenant_context(session, tenant_id)
                # The advisory lock exists even when this is the first event, preventing two genesis events.
                session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id), hashtext(:case_id))"),
                    {"tenant_id": tenant_id, "case_id": case_id},
                )
                previous = session.scalar(
                    select(AuditEventModel)
                    .where(
                        AuditEventModel.case_id == case_id,
                        AuditEventModel.tenant_id == tenant_id,
                    )
                    .order_by(AuditEventModel.sequence_no.desc())
                    .with_for_update()
                )
                sequence_no = (previous.sequence_no + 1) if previous else 1
                prev_hash = previous.event_hash if previous else hashlib.sha256(f"{self.genesis_prefix}:{case_id}".encode()).hexdigest()
                canonical = json.dumps(
                    {
                        "case_id": case_id,
                        "tenant_id": tenant_id,
                        "event_type": event_type,
                        "actor": actor,
                        "payload": safe_payload,
                        "prev_hash": prev_hash,
                        "created_at": created_at,
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                    default=str,
                )
                event_hash = hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()
                event = AuditEvent(
                    f"audit_{uuid4().hex}",
                    case_id,
                    tenant_id,
                    event_type,
                    actor,
                    safe_payload,
                    prev_hash,
                    event_hash,
                    created_at,
                )
                session.add(
                    AuditEventModel(
                        id=event.id,
                        case_id=case_id,
                        tenant_id=tenant_id,
                        event_type=event_type,
                        actor=actor,
                        payload=safe_payload,
                        prev_hash=prev_hash,
                        event_hash=event_hash,
                        sequence_no=sequence_no,
                        created_at=datetime.fromisoformat(created_at),
                    )
                )
                session.commit()
                return event
        except (OperationalError, DBAPIError) as exc:
            raise DomainError("AUDIT_PERSISTENCE_FAILED", "audit event could not be persisted", 503) from exc

    def list(self, case_id: str, tenant_id: str) -> list[AuditEvent]:
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            rows = session.scalars(
                select(AuditEventModel)
                .where(
                    AuditEventModel.case_id == case_id,
                    AuditEventModel.tenant_id == tenant_id,
                )
                .order_by(AuditEventModel.sequence_no)
            ).all()
            return [
                AuditEvent(
                    row.id,
                    row.case_id,
                    row.tenant_id,
                    row.event_type,
                    row.actor,
                    row.payload,
                    row.prev_hash,
                    row.event_hash,
                    row.created_at.isoformat(),
                )
                for row in rows
            ]

    def verify(self, case_id: str, tenant_id: str) -> bool:
        events = self.list(case_id, tenant_id)
        if not events:
            return False
        previous = None
        for event in events:
            expected_prev = previous or hashlib.sha256(f"{self.genesis_prefix}:{case_id}".encode()).hexdigest()
            if event.prev_hash != expected_prev:
                return False
            canonical = json.dumps(
                {
                    "case_id": event.case_id,
                    "tenant_id": event.tenant_id,
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "payload": event.payload,
                    "prev_hash": event.prev_hash,
                    "created_at": event.created_at,
                },
                sort_keys=True,
                ensure_ascii=True,
                default=str,
            )
            if hashlib.sha256(f"{event.prev_hash}{canonical}".encode()).hexdigest() != event.event_hash:
                return False
            previous = event.event_hash
        return True
