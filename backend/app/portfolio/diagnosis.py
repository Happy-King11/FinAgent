"""基于已校验静态行情的确定性组合集中度诊断。"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Iterable

from app.data.providers import PortfolioPositionRecord, QuoteRecord, SecurityMasterRecord
from app.data.quality import QualityReport


class DiagnosisStatus(StrEnum):
    COMPLETED = "completed"
    INSUFFICIENT_DATA = "insufficient_data"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RiskProfile:
    risk_level: str
    horizon_years: int
    liquidity_need: str
    confirmed: bool = False


@dataclass(frozen=True)
class PortfolioDiagnosisResult:
    diagnosis_id: str
    tenant_id: str
    portfolio_id: str
    status: DiagnosisStatus
    formula_version: str
    total_market_value: Decimal
    top1_weight: Decimal
    top3_weight: Decimal
    industry_exposure: dict[str, Decimal]
    warnings: tuple[str, ...]
    missing_fields: tuple[str, ...]
    quality: QualityReport
    risk_profile: RiskProfile | None
    as_of: str

    @staticmethod
    def _number(value: Decimal) -> float:
        return float(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    def as_dict(self) -> dict:
        return {
            "diagnosis_id": self.diagnosis_id,
            "portfolio_id": self.portfolio_id,
            "status": self.status.value,
            "formula_version": self.formula_version,
            "source_id": self.quality.source_id,
            "schema_version": "1.0.0",
            "total_market_value": self._number(self.total_market_value),
            "currency": "CNY",
            "top1_weight": self._number(self.top1_weight),
            "top3_weight": self._number(self.top3_weight),
            "industry_exposure": {key: self._number(value) for key, value in self.industry_exposure.items()},
            "warnings": list(self.warnings),
            "missing_fields": list(self.missing_fields),
            "quality": self.quality.as_dict(),
            "risk_profile": self.risk_profile.__dict__ if self.risk_profile else None,
            "as_of": self.as_of,
        }


class PortfolioDiagnosis:
    formula_version = "portfolio_concentration_v1.0.0"

    def run(
        self,
        *,
        diagnosis_id: str,
        tenant_id: str,
        portfolio_id: str,
        positions: Iterable[PortfolioPositionRecord],
        securities: Iterable[SecurityMasterRecord],
        quotes: Iterable[QuoteRecord],
        quality: QualityReport,
        risk_profile: RiskProfile | None,
    ) -> PortfolioDiagnosisResult:
        # 计算只消费结构化数据和质量报告，不接受模型生成的金融数字。
        position_list = list(positions)
        security_map = {item.security_id: item for item in securities}
        quote_map = {item.security_id: item for item in quotes}
        warnings = [issue.message for issue in quality.issues]
        missing: list[str] = []
        if not position_list:
            missing.append("portfolio_positions")
        if risk_profile is None or not risk_profile.confirmed:
            warnings.append("风险画像未确认，结果不能作为个性化投资建议。")
        values: list[tuple[PortfolioPositionRecord, Decimal]] = []
        for position in position_list:
            if position.market_value <= 0:
                missing.append(f"market_value:{position.security_id}")
                continue
            if position.security_id not in security_map:
                missing.append(f"security_master:{position.security_id}")
                continue
            if position.security_id not in quote_map and security_map[position.security_id].asset_class == "equity":
                missing.append(f"quote:{position.security_id}")
                continue
            values.append((position, Decimal(str(position.market_value))))
        total = sum((value for _, value in values), Decimal("0"))
        # 权重按 Decimal 计算，避免二进制浮点误差影响审计结果。
        weights = sorted((value / total for _, value in values), reverse=True) if total else []
        top1 = weights[0] if weights else Decimal("0")
        top3 = sum(weights[:3], Decimal("0"))
        industries: dict[str, Decimal] = {}
        if total:
            for position, value in values:
                security = security_map[position.security_id]
                label = security.industry_name or "未分类"
                industries[label] = industries.get(label, Decimal("0")) + value / total
        if top1 > Decimal("0.50"):
            warnings.append("单一持仓权重超过 50%，需要人工复核。")
        if any(weight > Decimal("0.30") for weight in industries.values()):
            warnings.append("单一行业暴露超过 30%，需要人工复核。")
        status = DiagnosisStatus.INSUFFICIENT_DATA if missing or quality.status == "failed" else DiagnosisStatus.COMPLETED
        if status == DiagnosisStatus.COMPLETED and any("需要人工复核" in item for item in warnings):
            status = DiagnosisStatus.HUMAN_REVIEW
        as_of = max((position.as_of for position, _ in values), default="")
        return PortfolioDiagnosisResult(diagnosis_id, tenant_id, portfolio_id, status, self.formula_version, total, top1, top3, industries, tuple(warnings), tuple(sorted(set(missing))), quality, risk_profile, as_of)
