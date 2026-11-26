"""Eight-scene routing and deterministic Risk Agent boundary."""

import pytest

from app.agents.intents import IntentRegistry
from app.agents.risk import RiskAgent
from app.agents.router import IntentRouter
from app.api.deps import container
from app.application.consultation_service import ConsultationService
from app.risk import RiskDisposition, RiskPolicyInput, RiskSubjectType
from app.tools.gateway import ToolExecutionContext


SCENES = {
    "single_stock_research",
    "product_explanation",
    "financial_knowledge",
    "portfolio_diagnosis",
    "valuation_analysis",
    "financial_statement_analysis",
    "risk_assessment",
    "compliance_consultation",
}


def test_registry_exposes_exactly_eight_internal_pilot_scenes():
    assert {item.intent_id for item in IntentRegistry().all()} == SCENES


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("请做这只股票的单股基本面研究", "single_stock_research"),
        ("解释这个基金产品的费用和流动性", "product_explanation"),
        ("什么是久期，请解释这个金融知识概念", "financial_knowledge"),
        ("诊断我的投资组合集中度和行业暴露", "portfolio_diagnosis"),
        ("使用 DCF 和 WACC 做估值分析", "valuation_analysis"),
        ("分析这份财报的利润表和现金流量表", "financial_statement_analysis"),
        ("进行风险评估、风险测评并说明承受能力", "risk_assessment"),
        ("解释适当性和合规监管要求", "compliance_consultation"),
    ],
)
def test_router_covers_each_scene(question: str, expected: str):
    route = IntentRouter().route(question, "trace-eight-scenes")
    assert route.primary_intent == expected
    assert route.candidate_pipelines == (f"{expected}@1.0.0",)
    assert route.requires_clarification is False


def test_all_scene_pipeline_contracts_are_registered():
    for scene in SCENES:
        manifest = container.pipeline_registry.manifest(f"{scene}@1.0.0")
        assert manifest.supported_intents == (scene,)
        assert manifest.audit_required is True
        assert manifest.output_schema.endswith("Result")


def test_risk_agent_cannot_override_deterministic_policy():
    blocked = RiskAgent().assess(
        RiskPolicyInput(RiskSubjectType.CONSULTATION, compliance_decision="block")
    ).as_dict()
    assert blocked["risk_level"] == "high"
    assert blocked["disposition"] == RiskDisposition.BLOCK
    assert blocked["decision_source"] == "deterministic_policy"
    assert blocked["can_override_policy"] is False

    incomplete = RiskAgent().assess(
        RiskPolicyInput(
            RiskSubjectType.SECURITY,
            missing_fields=("valuation_inputs",),
            evidence_required=True,
            evidence_count=0,
        )
    ).as_dict()
    assert incomplete["risk_level"] == "medium"
    assert set(incomplete["reason_codes"]) == {"AUTHORIZED_EVIDENCE_MISSING", "REQUIRED_INPUT_MISSING"}


def test_consultation_exposes_pipeline_and_risk_outputs():
    case = ConsultationService(container).create(
        tenant_id="tenant-demo",
        user_id="dev-user",
        question="请解释示例基金产品的费用和流动性",
    )
    assert case.intent == "product_explanation"
    assert case.result["scene_id"] == "product_explanation"
    assert case.risk_assessment["subject_type"] == "product"
    assert case.risk_assessment["can_override_policy"] is False


def test_finance_engine_is_exposed_through_governed_tools():
    result = container.tool_gateway.execute(
        "dcf_calculate",
        context=ToolExecutionContext("tenant-demo", allowed_tools=frozenset({"dcf_calculate"})),
        free_cash_flows=[100.0, 110.0, 120.0],
        wacc=0.10,
        terminal_growth=0.03,
        net_debt=50.0,
        shares_outstanding=100.0,
        currency="CNY",
        period="FY2026",
        data_sources=["dev_fixture"],
    )
    assert result["status"] == "completed"
    assert result["formula_version"] == "dcf_v1.0.0"
    assert result["data_sources"] == ["dev_fixture"]
