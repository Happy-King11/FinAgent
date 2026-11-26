"""Deterministic DCF valuation using Decimal arithmetic."""

from decimal import Decimal

from app.finance.types import FinanceResult, decimal


class DCFEngine:
    formula_version = "dcf_v1.0.0"

    def calculate(self, *, free_cash_flows: list[float], wacc: float, terminal_growth: float, net_debt: float = 0, shares_outstanding: float | None = None, currency: str | None = None, period: str | None = None, data_sources: tuple[str, ...] = ()) -> FinanceResult:
        flows = [decimal(value) for value in (free_cash_flows or [])]
        wacc_d, growth_d, debt_d, shares_d = decimal(wacc), decimal(terminal_growth), decimal(net_debt), decimal(shares_outstanding)
        missing = []
        if not flows or any(value is None for value in flows):
            missing.append("free_cash_flows")
        if shares_d is None:
            missing.append("shares_outstanding")
        if wacc_d is None:
            missing.append("wacc")
        if growth_d is None:
            missing.append("terminal_growth")
        if missing:
            return FinanceResult("insufficient_data", "target_price_dcf", None, self.formula_version, missing_fields=tuple(missing), currency=currency, unit="per_share", period=period, data_sources=data_sources)
        if wacc_d <= growth_d or wacc_d <= 0 or shares_d <= 0 or debt_d is None:
            return FinanceResult("insufficient_data", "target_price_dcf", None, self.formula_version, warnings=("WACC must exceed terminal growth and all values must be finite",), currency=currency, unit="per_share", period=period, data_sources=data_sources)
        pv = sum((cash_flow / (Decimal(1) + wacc_d) ** period_no for period_no, cash_flow in enumerate(flows, 1)), Decimal(0))
        terminal = flows[-1] * (Decimal(1) + growth_d) / (wacc_d - growth_d)
        value = (pv + terminal / (Decimal(1) + wacc_d) ** len(flows) - debt_d) / shares_d
        return FinanceResult("completed", "target_price_dcf", value, self.formula_version, {"wacc": str(wacc_d), "terminal_growth": str(growth_d), "net_debt": str(debt_d)}, currency=currency, unit="per_share", period=period, data_sources=data_sources, confidence="medium")
