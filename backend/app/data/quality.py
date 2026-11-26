"""行情和主数据质量门禁，阻止未经校验的数据进入组合计算。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.data.contracts import load_data_source_contract
from app.data.providers import QuoteRecord, SecurityMasterRecord


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str
    field: str | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message, "severity": self.severity}
        if self.field:
            result["field"] = self.field
        return result


@dataclass(frozen=True)
class QualityReport:
    status: str
    issues: tuple[QualityIssue, ...]
    checked_at: str
    source_id: str = ""
    source_as_of: str = ""

    def as_dict(self) -> dict:
        return {"status": self.status, "issues": [issue.as_dict() for issue in self.issues], "checked_at": self.checked_at, "source_id": self.source_id, "source_as_of": self.source_as_of}


class DataQualityGate:
    def validate(
        self,
        securities: Iterable[SecurityMasterRecord],
        quotes: Iterable[QuoteRecord],
        *,
        source_id: str,
        source_as_of: datetime,
        max_age_days: int = 3650,
    ) -> QualityReport:
        # 先检查来源和时效，再检查字段、映射、数值、币种等约束。
        issues: list[QualityIssue] = []
        try:
            contract = load_data_source_contract(source_id)
        except ValueError:
            contract = None
            issues.append(QualityIssue("UNKNOWN_SOURCE_CONTRACT", "数据源未配置字段级契约", severity="error"))
        if contract is not None and not contract.authorized:
            issues.append(QualityIssue("UNAUTHORIZED_SOURCE", "数据源授权范围不允许进入当前计算链路", severity="error"))
        if contract is not None and contract.max_age_days and max_age_days == 3650:
            max_age_days = contract.max_age_days
        security_list = list(securities)
        quote_list = list(quotes)
        security_ids = {item.security_id for item in security_list}
        if not source_id:
            issues.append(QualityIssue("UNAUTHORIZED_SOURCE", "数据源未声明授权范围", severity="error"))
        age_days = (datetime.now(timezone.utc) - source_as_of.astimezone(timezone.utc)).days
        if age_days > max_age_days:
            issues.append(QualityIssue("STALE_DATA", f"数据源已超过 {max_age_days} 天未更新", severity="error"))
        for security in security_list:
            if not security.security_id or not security.currency:
                issues.append(QualityIssue("MISSING_REQUIRED_FIELD", "证券主数据缺少 ID 或币种", security.security_id))
        for quote in quote_list:
            if quote.security_id not in security_ids:
                issues.append(QualityIssue("UNKNOWN_SECURITY", f"行情证券未在主数据中映射: {quote.security_id}", quote.security_id))
            if quote.high < max(quote.open, quote.close) or quote.low > min(quote.open, quote.close):
                issues.append(QualityIssue("INVALID_OHLC", f"行情 OHLC 约束失败: {quote.security_id}", quote.security_id))
            if quote.close <= 0 or quote.volume < 0 or quote.amount < 0:
                issues.append(QualityIssue("INVALID_QUOTE_VALUE", f"行情数值非法: {quote.security_id}", quote.security_id))
            if quote.currency != "CNY":
                issues.append(QualityIssue("CURRENCY_MISMATCH", f"当前组合只支持 CNY，收到 {quote.currency}", quote.security_id))
        status = "passed" if not issues else "failed"
        return QualityReport(status, tuple(issues), datetime.now(timezone.utc).isoformat(), source_id, source_as_of.isoformat())
