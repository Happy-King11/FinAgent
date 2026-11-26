"""租户范围的组合诊断结果仓储。"""

from decimal import Decimal

from app.data.quality import QualityIssue, QualityReport
from app.portfolio.diagnosis import DiagnosisStatus, PortfolioDiagnosisResult, RiskProfile
from app.repositories.memory import TenantMemoryRepository
from app.repositories.workflow import MemoryWorkflowRecordStore, SQLWorkflowRecordStore


class PortfolioDiagnosisRepository(TenantMemoryRepository[PortfolioDiagnosisResult]):
    """进程内组合诊断仓储，供开发和单元测试使用。"""


class PersistentPortfolioDiagnosisRepository:
    """Store diagnosis payloads in the tenant-scoped domain-record table."""

    record_type = "portfolio_diagnosis"

    def __init__(self, records: SQLWorkflowRecordStore | MemoryWorkflowRecordStore) -> None:
        self.records = records

    def add(self, result: PortfolioDiagnosisResult, item_id: str) -> PortfolioDiagnosisResult:
        self.records.put(self.record_type, item_id, result.tenant_id, result.as_dict())
        return result

    def get(self, item_id: str, tenant_id: str) -> PortfolioDiagnosisResult:
        return self._from_payload(self.records.get(self.record_type, item_id, tenant_id), tenant_id)

    @staticmethod
    def _from_payload(payload: dict, tenant_id: str) -> PortfolioDiagnosisResult:
        quality_payload = payload.get("quality") or {}
        quality = QualityReport(
            status=quality_payload.get("status", "failed"),
            issues=tuple(QualityIssue(**issue) for issue in quality_payload.get("issues", [])),
            checked_at=quality_payload.get("checked_at", ""),
            source_id=payload.get("source_id", quality_payload.get("source_id", "")),
            source_as_of=quality_payload.get("source_as_of", ""),
        )
        profile_payload = payload.get("risk_profile")
        profile = RiskProfile(**profile_payload) if profile_payload else None
        industry = {key: Decimal(str(value)) for key, value in (payload.get("industry_exposure") or {}).items()}
        return PortfolioDiagnosisResult(
            diagnosis_id=payload["diagnosis_id"],
            tenant_id=tenant_id,
            portfolio_id=payload["portfolio_id"],
            status=DiagnosisStatus(payload["status"]),
            formula_version=payload["formula_version"],
            total_market_value=Decimal(str(payload.get("total_market_value", 0))),
            top1_weight=Decimal(str(payload.get("top1_weight", 0))),
            top3_weight=Decimal(str(payload.get("top3_weight", 0))),
            industry_exposure=industry,
            warnings=tuple(payload.get("warnings", [])),
            missing_fields=tuple(payload.get("missing_fields", [])),
            quality=quality,
            risk_profile=profile,
            as_of=payload.get("as_of", ""),
        )
