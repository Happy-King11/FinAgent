"""不可变审计事件和按案例串联的 SHA-256 哈希链。"""

import hashlib
import json
from dataclasses import dataclass
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class AuditEvent:
    id: str
    case_id: str
    tenant_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    prev_hash: str
    event_hash: str
    created_at: str


class AuditLog:
    """Append-only audit log with a per-case SHA-256 hash chain."""

    def __init__(self, genesis_prefix: str = "financial-agent:audit:genesis") -> None:
        self._events: dict[str, list[AuditEvent]] = {}
        self._genesis_prefix = genesis_prefix
        self._lock = threading.RLock()

    def append(self, *, case_id: str, tenant_id: str, event_type: str, actor: str, payload: dict[str, Any]) -> AuditEvent:
        # 每个案例独立从 genesis 开始，便于按案例导出和校验。
        with self._lock:
            previous = self._events.get(case_id, [])
            safe_payload = _safe_payload(payload)
            prev_hash = previous[-1].event_hash if previous else hashlib.sha256(f"{self._genesis_prefix}:{case_id}".encode()).hexdigest()
            created_at = datetime.now(timezone.utc).isoformat()
            canonical = json.dumps({"case_id": case_id, "tenant_id": tenant_id, "event_type": event_type, "actor": actor, "payload": safe_payload, "prev_hash": prev_hash, "created_at": created_at}, sort_keys=True, ensure_ascii=True, default=str)
            event_hash = hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()
            event = AuditEvent(f"audit_{uuid4().hex}", case_id, tenant_id, event_type, actor, safe_payload, prev_hash, event_hash, created_at)
            self._events.setdefault(case_id, []).append(event)
            return event

    def list(self, case_id: str, tenant_id: str) -> list[AuditEvent]:
        return [event for event in self._events.get(case_id, []) if event.tenant_id == tenant_id]

    def verify(self, case_id: str, tenant_id: str) -> bool:
        # 不存在的链不能被视为已验证。
        events = self.list(case_id, tenant_id)
        if not events:
            return False
        previous = None
        for event in events:
            expected_prev = previous or hashlib.sha256(f"{self._genesis_prefix}:{case_id}".encode()).hexdigest()
            if event.prev_hash != expected_prev:
                return False
            canonical = json.dumps({"case_id": event.case_id, "tenant_id": event.tenant_id, "event_type": event.event_type, "actor": event.actor, "payload": event.payload, "prev_hash": event.prev_hash, "created_at": event.created_at}, sort_keys=True, ensure_ascii=True, default=str)
            if hashlib.sha256(f"{event.prev_hash}{canonical}".encode()).hexdigest() != event.event_hash:
                return False
            previous = event.event_hash
        return True


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist bounded event metadata without raw consultation or secret content."""
    blocked = {"api_key", "authorization", "token", "secret", "password", "question", "answer", "content", "holdings", "prompt"}
    result: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = str(key).lower()
        if normalized in blocked or any(part in normalized for part in ("api_key", "authorization", "password", "secret", "token")):
            result[str(key)] = "[redacted]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = value if not isinstance(value, str) or len(value) <= 256 else value[:256] + "..."
        elif isinstance(value, (list, tuple)):
            result[str(key)] = {"count": len(value)}
        elif isinstance(value, dict):
            result[str(key)] = _safe_payload(value)
        else:
            result[str(key)] = str(value)[:256]
    return result
