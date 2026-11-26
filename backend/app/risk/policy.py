"""Deterministic policy boundary for the five supported risk subjects."""

from dataclasses import dataclass
from enum import StrEnum

from app.core.constants import RiskLevel


class RiskSubjectType(StrEnum):
    USER = "user"
    PRODUCT = "product"
    SECURITY = "security"
    PORTFOLIO = "portfolio"
    CONSULTATION = "consultation"


class RiskDisposition(StrEnum):
    ALLOW = "allow"
    DISCLOSE = "disclose"
    HUMAN_REVIEW = "human_review"
    BLOCK = "block"


@dataclass(frozen=True)
class RiskPolicyInput:
    subject_type: RiskSubjectType
    compliance_decision: str = "allow"
    data_quality_status: str = "not_checked"
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_required: bool = False
    evidence_count: int = 0


@dataclass(frozen=True)
class RiskPolicyDecision:
    subject_type: RiskSubjectType
    risk_level: RiskLevel
    disposition: RiskDisposition
    reason_codes: tuple[str, ...]
    policy_version: str

    def as_dict(self) -> dict:
        return {
            "subject_type": self.subject_type.value,
            "risk_level": self.risk_level.value,
            "disposition": self.disposition.value,
            "reason_codes": list(self.reason_codes),
            "policy_version": self.policy_version,
        }


class RiskPolicyEngine:
    """Assign risk and disposition without using model-generated numbers."""

    policy_version = "risk_policy_v1.0.0"

    def evaluate(self, payload: RiskPolicyInput) -> RiskPolicyDecision:
        reasons: list[str] = []
        if payload.compliance_decision == "block":
            return self._decision(payload, RiskLevel.HIGH, RiskDisposition.BLOCK, ("COMPLIANCE_BLOCKED",))
        if payload.compliance_decision == "require_approval":
            return self._decision(payload, RiskLevel.HIGH, RiskDisposition.HUMAN_REVIEW, ("COMPLIANCE_REVIEW_REQUIRED",))
        if payload.data_quality_status == "failed":
            return self._decision(payload, RiskLevel.HIGH, RiskDisposition.HUMAN_REVIEW, ("DATA_QUALITY_FAILED",))
        if payload.evidence_required and payload.evidence_count == 0:
            reasons.append("AUTHORIZED_EVIDENCE_MISSING")
        if payload.missing_fields:
            reasons.append("REQUIRED_INPUT_MISSING")
        if reasons:
            return self._decision(payload, RiskLevel.MEDIUM, RiskDisposition.DISCLOSE, tuple(reasons))
        if payload.warnings:
            return self._decision(payload, RiskLevel.MEDIUM, RiskDisposition.DISCLOSE, ("RISK_WARNING_PRESENT",))
        return self._decision(payload, RiskLevel.LOW, RiskDisposition.ALLOW, ())

    def _decision(
        self,
        payload: RiskPolicyInput,
        level: RiskLevel,
        disposition: RiskDisposition,
        reasons: tuple[str, ...],
    ) -> RiskPolicyDecision:
        return RiskPolicyDecision(payload.subject_type, level, disposition, reasons, self.policy_version)
