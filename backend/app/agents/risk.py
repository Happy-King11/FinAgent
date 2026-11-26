"""Risk Agent: explain deterministic policy results without overriding them."""

from dataclasses import dataclass

from app.risk.policy import RiskPolicyDecision, RiskPolicyEngine, RiskPolicyInput


@dataclass(frozen=True)
class RiskAssessment:
    decision: RiskPolicyDecision
    summary: str
    warnings: tuple[str, ...]
    agent_version: str = "risk_agent_v1.0.0"

    def as_dict(self) -> dict:
        return {
            **self.decision.as_dict(),
            "summary": self.summary,
            "warnings": list(self.warnings),
            "agent_version": self.agent_version,
            "decision_source": "deterministic_policy",
            "can_override_policy": False,
        }


class RiskAgent:
    """Produce a user-facing explanation of an immutable policy decision."""

    def __init__(self, policy: RiskPolicyEngine | None = None) -> None:
        self.policy = policy or RiskPolicyEngine()

    def assess(self, payload: RiskPolicyInput) -> RiskAssessment:
        decision = self.policy.evaluate(payload)
        reason_text = {
            "COMPLIANCE_BLOCKED": "合规规则已阻断该请求。",
            "COMPLIANCE_REVIEW_REQUIRED": "该请求需要人工合规复核。",
            "DATA_QUALITY_FAILED": "数据质量检查未通过，不能形成可依赖结论。",
            "AUTHORIZED_EVIDENCE_MISSING": "缺少授权证据，结论只能披露资料不足。",
            "REQUIRED_INPUT_MISSING": "缺少必需的结构化输入，未执行确定性计算。",
            "RISK_WARNING_PRESENT": "结果包含需要向用户披露的风险提示。",
        }
        warnings = tuple(reason_text[code] for code in decision.reason_codes if code in reason_text)
        summary = "未发现需要额外升级处理的风险。" if not warnings else "".join(warnings)
        return RiskAssessment(decision, summary, warnings)
