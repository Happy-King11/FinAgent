"""工具调用和输出后审核使用的结构化 Guardrail 决策。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    decision: str
    rule_ids: tuple[str, ...] = ()
    reason: str | None = None
    required_action: str | None = None
    trace_id: str | None = None
    audit_event_id: str | None = None

    def as_dict(self) -> dict:
        return {"decision": self.decision, "rule_ids": list(self.rule_ids), "reason": self.reason, "required_action": self.required_action, "trace_id": self.trace_id, "audit_event_id": self.audit_event_id}
