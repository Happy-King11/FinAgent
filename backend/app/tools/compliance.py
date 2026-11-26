"""从版本化 JSON 加载确定性合规规则，并优先执行硬阻断规则。"""

from dataclasses import dataclass
import json
import re
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: str
    patterns: tuple[str, ...]
    action: str
    severity: str
    reason: str
    rewrite_hint: str | None = None
    priority: int = 100


def load_rules(directory: Path | None = None) -> tuple[Rule, ...]:
    """加载 configs/compliance_rules 下的规则；没有资产时启动失败。"""
    root = directory or Path(__file__).resolve().parents[2] / "configs" / "compliance_rules"
    rules: list[Rule] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        trigger = payload.get("trigger", {})
        action = payload.get("action")
        if action not in {"block", "rewrite", "require_disclosure", "require_human", "require_profile"}:
            raise ValueError(f"invalid compliance action in {path.name}")
        rules.append(Rule(payload["rule_id"], payload["version"], tuple(trigger.get("patterns", [])), action, payload.get("severity", "high"), payload.get("description", ""), payload.get("rewrite_hint"), int(payload.get("priority", 100))))
    if not rules:
        raise RuntimeError(f"no compliance rule assets found in {root}")
    return tuple(rules)


@dataclass(frozen=True)
class ComplianceDecision:
    decision: str
    rule_ids: tuple[str, ...]
    reason: str | None = None
    required_action: str | None = None
    rewritten_text: str | None = None

    def as_dict(self) -> dict:
        return {"decision": self.decision, "rule_ids": list(self.rule_ids), "reason": self.reason, "required_action": self.required_action, "rewritten_text": self.rewritten_text}


class ComplianceEngine:
    def __init__(self, rules: tuple[Rule, ...] | None = None) -> None:
        self.rules = rules or load_rules()

    def check(self, text: str, *, phase: str = "pre") -> ComplianceDecision:
        # 关键词命中即可触发规则；LLM 不能否决硬规则结果。
        matches = [rule for rule in self.rules if any(re.search(re.escape(pattern), text, re.IGNORECASE) for pattern in rule.patterns)]
        if not matches:
            return ComplianceDecision("allow", ())
        matches.sort(key=lambda item: (0 if item.action == "block" else 1, item.priority))
        block = next((rule for rule in matches if rule.action == "block"), None)
        if block:
            return ComplianceDecision("block", tuple(r.rule_id for r in matches), block.reason, "remove_prohibited_expression")
        human = next((rule for rule in matches if rule.action == "require_human"), None)
        if human:
            return ComplianceDecision("require_approval", tuple(r.rule_id for r in matches), human.reason, "human_review")
        rewrite = matches[0]
        return ComplianceDecision("rewrite", tuple(r.rule_id for r in matches), rewrite.reason, "apply_disclosure", rewrite.rewrite_hint)
