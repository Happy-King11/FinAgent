"""Deterministic scenario analysis using Decimal arithmetic."""

from app.finance.types import FinanceResult, decimal


class ScenarioEngine:
    formula_version = "scenario_v1.0.0"

    def calculate(self, *, base_value: float, scenarios: dict[str, float], currency: str | None = None, period: str | None = None, data_sources: tuple[str, ...] = ()) -> FinanceResult:
        base = decimal(base_value)
        changes = {name: decimal(change) for name, change in (scenarios or {}).items()}
        if base is None:
            return FinanceResult("insufficient_data", "scenario_values", None, self.formula_version, missing_fields=("base_value",), currency=currency, unit="value", period=period, data_sources=data_sources)
        if not changes or any(value is None for value in changes.values()):
            return FinanceResult("insufficient_data", "scenario_values", None, self.formula_version, missing_fields=("scenarios",), currency=currency, unit="value", period=period, data_sources=data_sources)
        values = {name: base * (1 + change) for name, change in changes.items()}
        return FinanceResult("completed", "scenario_values", base, self.formula_version, {"scenario_values": {name: str(value) for name, value in values.items()}}, currency=currency, unit="value", period=period, data_sources=data_sources, confidence="medium")
