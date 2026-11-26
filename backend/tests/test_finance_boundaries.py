"""Boundary and invalid-input regression tests for finance engines."""

from decimal import Decimal

from app.finance.comparables import ComparableCompanyEngine
from app.finance.dcf import DCFEngine
from app.finance.scenario import ScenarioEngine
from app.finance.wacc import WACCEngine


def test_finance_results_are_decimal_and_include_metadata():
    result = DCFEngine().calculate(free_cash_flows=[10, 11], wacc=0.1, terminal_growth=0.02, shares_outstanding=10, currency="USD", period="FY2025-FY2026", data_sources=("fixture",))
    assert isinstance(result.value, Decimal)
    assert result.currency == "USD"
    assert result.unit == "per_share"
    assert result.period == "FY2025-FY2026"
    assert result.data_sources == ("fixture",)


def test_engines_reject_non_finite_and_invalid_inputs():
    assert DCFEngine().calculate(free_cash_flows=[float("nan")], wacc=0.1, terminal_growth=0.02, shares_outstanding=10).status == "insufficient_data"
    assert WACCEngine().calculate(cost_of_equity=0.1, cost_of_debt=0.05, tax_rate=None, equity_value=75, debt_value=25).status == "insufficient_data"
    assert ComparableCompanyEngine().calculate(peer_multiples=[0, 10], target_metric=5).status == "insufficient_data"
    assert ScenarioEngine().calculate(base_value=100, scenarios={"base": float("inf")}).status == "insufficient_data"
