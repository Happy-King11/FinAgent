"""组合诊断应用服务：协调数据质量、确定性计算、复核和审计。"""

from uuid import uuid4

from app.application.container import Container
from app.core.exceptions import DomainError, NotFoundError
from app.portfolio.diagnosis import DiagnosisStatus, PortfolioDiagnosisResult, RiskProfile


class PortfolioDiagnosisService:
    def __init__(self, container: Container) -> None:
        self.container = container

    def create(self, *, tenant_id: str, user_id: str, portfolio_id: str, risk_profile: RiskProfile | None) -> PortfolioDiagnosisResult:
        # 先完成数据质量门禁，再把结构化数据交给组合计算模块。
        diagnosis_id = f"diagnosis_{uuid4().hex}"
        positions = self.container.data_provider.list_positions(portfolio_id)
        securities = self.container.data_provider.list_securities()
        quotes = self.container.data_provider.list_quotes()
        source_as_of = self.container.data_provider.source_as_of()
        quality = self.container.quality_gate.validate(securities, quotes, source_id=self.container.data_provider.source_id, source_as_of=source_as_of)
        result = self.container.portfolio_diagnosis.run(
            diagnosis_id=diagnosis_id,
            tenant_id=tenant_id,
            portfolio_id=portfolio_id,
            positions=positions,
            securities=securities,
            quotes=quotes,
            quality=quality,
            risk_profile=risk_profile,
        )
        self.container.portfolio_diagnoses.add(result, diagnosis_id)
        self.container.audit.append(case_id=diagnosis_id, tenant_id=tenant_id, event_type="portfolio.diagnosis.created", actor=user_id, payload=result.as_dict())
        return result

    def get(self, diagnosis_id: str, tenant_id: str) -> PortfolioDiagnosisResult:
        return self.container.portfolio_diagnoses.get(diagnosis_id, tenant_id)

    def review(self, *, diagnosis_id: str, tenant_id: str, reviewer_id: str, decision: str, note: str) -> PortfolioDiagnosisResult:
        # 复核通过后生成新版本结果，保留原结果和审计事件。
        result = self.get(diagnosis_id, tenant_id)
        if result.status not in {DiagnosisStatus.HUMAN_REVIEW, DiagnosisStatus.COMPLETED}:
            raise DomainError("INVALID_STATE", f"诊断当前状态不可复核: {result.status.value}", 409)
        if decision not in {"approve", "reject"}:
            raise DomainError("INVALID_ARGUMENT", "decision must be approve or reject", 422)
        updated = PortfolioDiagnosisResult(
            result.diagnosis_id, result.tenant_id, result.portfolio_id,
            DiagnosisStatus.APPROVED if decision == "approve" else DiagnosisStatus.REJECTED,
            result.formula_version, result.total_market_value, result.top1_weight, result.top3_weight,
            result.industry_exposure, result.warnings + ((f"人工复核备注：{note}",) if note else ()), result.missing_fields,
            result.quality, result.risk_profile, result.as_of,
        )
        self.container.portfolio_diagnoses.add(updated, diagnosis_id)
        self.container.audit.append(case_id=diagnosis_id, tenant_id=tenant_id, event_type="portfolio.diagnosis.reviewed", actor=reviewer_id, payload={"decision": decision, "note": note, "status": updated.status.value})
        return updated
