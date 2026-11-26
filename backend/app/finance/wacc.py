"""Deterministic WACC calculation using Decimal arithmetic."""

from app.finance.types import FinanceResult, decimal


class WACCEngine:
    formula_version = "wacc_v1.0.0"

    def calculate(self, *, cost_of_equity: float, cost_of_debt: float, tax_rate: float, equity_value: float, debt_value: float, currency: str | None = None, period: str | None = None, data_sources: tuple[str, ...] = ()) -> FinanceResult:
        inputs = {"cost_of_equity": decimal(cost_of_equity), "cost_of_debt": decimal(cost_of_debt), "tax_rate": decimal(tax_rate), "equity_value": decimal(equity_value), "debt_value": decimal(debt_value)}
        missing = tuple(name for name, value in inputs.items() if value is None)
        if missing:
            return FinanceResult("insufficient_data", "wacc", None, self.formula_version, missing_fields=missing, currency=currency, unit="ratio", period=period, data_sources=data_sources)
        total = inputs["equity_value"] + inputs["debt_value"]
        if total <= 0 or inputs["tax_rate"] < 0 or inputs["tax_rate"] > 1:
            return FinanceResult("insufficient_data", "wacc", None, self.formula_version, missing_fields=("capital_total",), warnings=("capital total must be positive and tax rate must be between 0 and 1",), currency=currency, unit="ratio", period=period, data_sources=data_sources)
        value = inputs["equity_value"] / total * inputs["cost_of_equity"] + inputs["debt_value"] / total * inputs["cost_of_debt"] * (1 - inputs["tax_rate"])
        assumptions = {key: str(value) for key, value in inputs.items() if key in {"cost_of_equity", "cost_of_debt", "tax_rate"}}
        return FinanceResult("completed", "wacc", value, self.formula_version, assumptions, currency=currency, unit="ratio", period=period, data_sources=data_sources, confidence="medium")
