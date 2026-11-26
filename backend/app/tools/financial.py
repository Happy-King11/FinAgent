"""ToolGateway adapters for deterministic Finance Engine calculations."""

from app.finance.comparables import ComparableCompanyEngine
from app.finance.dcf import DCFEngine
from app.finance.scenario import ScenarioEngine
from app.finance.wacc import WACCEngine
from app.tools.gateway import ToolGateway
from app.tools.registry import ToolManifest


_FINANCE_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["status", "metric", "formula_version"],
    "properties": {
        "status": {"type": "string"},
        "metric": {"type": "string"},
        "formula_version": {"type": "string"},
    },
}


def register_finance_tools(gateway: ToolGateway) -> None:
    """Register pure, replayable calculations without exposing engine mutation."""
    dcf = DCFEngine()
    wacc = WACCEngine()
    comparables = ComparableCompanyEngine()
    scenario_engine = ScenarioEngine()

    gateway.register(
        "dcf_calculate",
        lambda free_cash_flows, wacc, terminal_growth, net_debt=0, shares_outstanding=None, currency=None, period=None, data_sources=(): dcf.calculate(
            free_cash_flows=free_cash_flows,
            wacc=wacc,
            terminal_growth=terminal_growth,
            net_debt=net_debt,
            shares_outstanding=shares_outstanding,
            currency=currency,
            period=period,
            data_sources=tuple(data_sources),
        ).as_dict(),
        ToolManifest(
            "dcf_calculate",
            risk_level="L1",
            input_schema={
                "type": "object",
                "required": ["free_cash_flows", "wacc", "terminal_growth", "shares_outstanding"],
                "properties": {
                    "free_cash_flows": {"type": "array"},
                    "wacc": {"type": "number"},
                    "terminal_growth": {"type": "number"},
                    "net_debt": {"type": "number"},
                    "shares_outstanding": {"type": "number"},
                    "currency": {"type": "string"},
                    "period": {"type": "string"},
                    "data_sources": {"type": "array"},
                },
            },
            output_schema=_FINANCE_OUTPUT_SCHEMA,
        ),
    )
    gateway.register(
        "wacc_calculate",
        lambda cost_of_equity, cost_of_debt, tax_rate, equity_value, debt_value, currency=None, period=None, data_sources=(): wacc.calculate(
            cost_of_equity=cost_of_equity,
            cost_of_debt=cost_of_debt,
            tax_rate=tax_rate,
            equity_value=equity_value,
            debt_value=debt_value,
            currency=currency,
            period=period,
            data_sources=tuple(data_sources),
        ).as_dict(),
        ToolManifest(
            "wacc_calculate",
            risk_level="L1",
            input_schema={
                "type": "object",
                "required": ["cost_of_equity", "cost_of_debt", "tax_rate", "equity_value", "debt_value"],
                "properties": {
                    "cost_of_equity": {"type": "number"},
                    "cost_of_debt": {"type": "number"},
                    "tax_rate": {"type": "number"},
                    "equity_value": {"type": "number"},
                    "debt_value": {"type": "number"},
                    "currency": {"type": "string"},
                    "period": {"type": "string"},
                    "data_sources": {"type": "array"},
                },
            },
            output_schema=_FINANCE_OUTPUT_SCHEMA,
        ),
    )
    gateway.register(
        "comparable_valuation",
        lambda peer_multiples, target_metric, multiple_name="pe", currency=None, period=None, data_sources=(): comparables.calculate(
            peer_multiples=peer_multiples,
            target_metric=target_metric,
            multiple_name=multiple_name,
            currency=currency,
            period=period,
            data_sources=tuple(data_sources),
        ).as_dict(),
        ToolManifest(
            "comparable_valuation",
            risk_level="L1",
            input_schema={
                "type": "object",
                "required": ["peer_multiples", "target_metric"],
                "properties": {
                    "peer_multiples": {"type": "array"},
                    "target_metric": {"type": "number"},
                    "multiple_name": {"type": "string"},
                    "currency": {"type": "string"},
                    "period": {"type": "string"},
                    "data_sources": {"type": "array"},
                },
            },
            output_schema=_FINANCE_OUTPUT_SCHEMA,
        ),
    )
    gateway.register(
        "scenario_calculate",
        lambda base_value, scenarios: scenario_engine.calculate(base_value=base_value, scenarios=scenarios).as_dict(),
        ToolManifest(
            "scenario_calculate",
            risk_level="L1",
            input_schema={
                "type": "object",
                "required": ["base_value", "scenarios"],
                "properties": {"base_value": {"type": "number"}, "scenarios": {"type": "object"}},
            },
            output_schema=_FINANCE_OUTPUT_SCHEMA,
        ),
    )
