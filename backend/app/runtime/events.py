"""Replaceable in-process lifecycle event publication."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.runtime.context import RuntimeContext


EVENT_TYPES = frozenset(
    {
        "consultation.started",
        "consultation.classified",
        "consultation.compliance_checked",
        "consultation.step_started",
        "consultation.step_completed",
        "consultation.tool_started",
        "consultation.tool_completed",
        "consultation.tool_failed",
        "consultation.retry_scheduled",
        "consultation.fallback_selected",
        "consultation.quality_failed",
        "consultation.human_review_required",
        "consultation.status_changed",
        "consultation.completed",
        "consultation.failed",
    }
)


@dataclass(frozen=True)
class RuntimeEvent:
    event_type: str
    trace_id: str
    case_id: str
    tenant_id: str
    request_id: str = ""
    step_id: str = ""
    status: str = ""
    runtime_version: str = "1.0.0"
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"event_{uuid4().hex}")

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported runtime event: {self.event_type}")
        if not self.trace_id or not self.case_id or not self.tenant_id:
            raise ValueError("runtime event correlation identifiers are required")
        object.__setattr__(self, "payload", _safe_payload(self.payload))

    @classmethod
    def from_context(cls, context: RuntimeContext, event_type: str, *, payload: dict[str, Any] | None = None, step_id: str = "") -> "RuntimeEvent":
        return cls(
            event_type=event_type,
            trace_id=context.trace_id,
            case_id=context.case_id,
            tenant_id=context.tenant_id,
            request_id=context.request_id,
            step_id=step_id,
            status=context.status,
            payload=payload or {},
        )


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep operational events bounded and free of obvious sensitive fields."""
    blocked = {"api_key", "authorization", "token", "secret", "password", "question", "answer", "content", "holdings", "prompt"}
    result: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = str(key).lower()
        if normalized in blocked or any(part in normalized for part in ("api_key", "password", "authorization", "secret", "token")):
            result[str(key)] = "[redacted]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = value if not (isinstance(value, str) and len(value) > 256) else value[:256] + "..."
        elif isinstance(value, (list, tuple)):
            result[str(key)] = {"count": len(value)}
        elif isinstance(value, dict):
            result[str(key)] = _safe_payload(value)
        else:
            result[str(key)] = str(value)[:256]
    return result


class EventBus:
    """Synchronous publisher whose subscribers cannot break business execution."""

    def __init__(self, *, on_subscriber_error: Callable[[Exception, RuntimeEvent], None] | None = None) -> None:
        self._subscribers: list[Callable[[RuntimeEvent], None]] = []
        self._on_subscriber_error = on_subscriber_error

    def subscribe(self, handler: Callable[[RuntimeEvent], None]) -> Callable[[], None]:
        self._subscribers.append(handler)
        def unsubscribe() -> None:
            if handler in self._subscribers:
                self._subscribers.remove(handler)
        return unsubscribe

    def publish(self, event: RuntimeEvent) -> None:
        for handler in tuple(self._subscribers):
            try:
                handler(event)
            except Exception as exc:  # observers are never on the business path
                if self._on_subscriber_error is not None:
                    try:
                        self._on_subscriber_error(exc, event)
                    except Exception:
                        pass
