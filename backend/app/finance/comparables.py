"""Deterministic comparable-company valuation using Decimal arithmetic."""

from statistics import median

from app.finance.types import FinanceResult, decimal


class ComparableCompanyEngine:
    formula_version = "comps_v1.0.0"

    def calculate(self, *, peer_multiples: list[float], target_metric: float, multiple_name: str = "pe", currency: str | None = None, period: str | None = None, data_sources: tuple[str, ...] = ()) -> FinanceResult:
        multiples = [decimal(value) for value in (peer_multiples or [])]
        metric = decimal(target_metric)
        missing = []
        if not multiples or any(value is None for value in multiples):
            missing.append("peer_multiples")
        if metric is None:
            missing.append("target_metric")
        if missing:
            return FinanceResult("insufficient_data", f"target_value_{multiple_name}", None, self.formula_version, missing_fields=tuple(missing), currency=currency, unit="per_share", period=period, data_sources=data_sources)
        if any(value <= 0 for value in multiples) or metric <= 0:
            return FinanceResult("insufficient_data", f"target_value_{multiple_name}", None, self.formula_version, warnings=("multiples and target metric must be positive",), currency=currency, unit="per_share", period=period, data_sources=data_sources)
        multiple = decimal(median(multiples))
        return FinanceResult("completed", f"target_value_{multiple_name}", multiple * metric, self.formula_version, {"median_multiple": str(multiple), "peer_count": len(multiples)}, currency=currency, unit="per_share", period=period, data_sources=data_sources, confidence="medium")
