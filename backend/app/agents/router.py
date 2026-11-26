"""Versioned deterministic intent router."""

from dataclasses import dataclass

from app.agents.intents import IntentDefinition, IntentRegistry
from app.core.constants import RiskLevel


@dataclass(frozen=True)
class RouterResult:
    primary_intent: str
    secondary_intents: tuple[str, ...]
    confidence: float
    requires_clarification: bool
    requires_retrieval: bool
    requires_computation: bool
    requires_user_profile: bool
    requires_compliance_review: bool
    risk_level: RiskLevel
    candidate_pipelines: tuple[str, ...]
    trace_id: str
    router_version: str = "rules_v1.0.0"

    def as_dict(self) -> dict:
        return {
            "primary_intent": self.primary_intent,
            "secondary_intents": list(self.secondary_intents),
            "confidence": self.confidence,
            "requires_clarification": self.requires_clarification,
            "requires_retrieval": self.requires_retrieval,
            "requires_computation": self.requires_computation,
            "requires_user_profile": self.requires_user_profile,
            "requires_compliance_review": self.requires_compliance_review,
            "risk_level": self.risk_level.value,
            "candidate_pipelines": list(self.candidate_pipelines),
            "trace_id": self.trace_id,
            "router_version": self.router_version,
        }


class IntentRouter:
    def __init__(self, registry: IntentRegistry | None = None):
        self.registry = registry or IntentRegistry()

    def route(self, question: str, trace_id: str, requested_intent: str | None = None) -> RouterResult:
        """Route to one of the frozen scenes; an explicit intent still uses policy flags."""
        text = question.lower()
        if requested_intent is not None:
            try:
                definition = self.registry.get(requested_intent)
            except KeyError as exc:
                raise ValueError(f"unknown requested intent: {requested_intent}") from exc
            return RouterResult(
                definition.intent_id,
                (),
                0.99,
                False,
                definition.requires_retrieval,
                definition.requires_computation,
                definition.requires_user_profile,
                definition.requires_compliance_review,
                RiskLevel(definition.risk_level),
                (definition.pipeline_ref,),
                trace_id,
            )
        scored: list[tuple[int, IntentDefinition]] = []
        for definition in self.registry.all():
            score = sum(1 for keyword in definition.keywords if keyword.lower() in text)
            if score:
                scored.append((score, definition))
        scored.sort(key=lambda item: (-item[0], item[1].intent_id))
        if not scored:
            return RouterResult("financial_knowledge", (), 0.60, True, True, False, False, True, RiskLevel.LOW, ("financial_knowledge@1.0.0",), trace_id)
        score, definition = scored[0]
        confidence = min(0.99, 0.70 + 0.10 * score)
        secondary = tuple(item.intent_id for _, item in scored[1:])
        return RouterResult(definition.intent_id, secondary, confidence, confidence < 0.80, definition.requires_retrieval, definition.requires_computation, definition.requires_user_profile, definition.requires_compliance_review, RiskLevel(definition.risk_level), (definition.pipeline_ref,), trace_id)
