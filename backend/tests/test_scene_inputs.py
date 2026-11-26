"""八场景强类型输入和估值 Pipeline 的回归测试。"""

import pytest
from pydantic import ValidationError

from app.api.v1.schemas import ConsultationCreate, ValuationAnalysisInput
from app.api.deps import container
from app.application.consultation_service import ConsultationService


def test_scene_input_is_discriminated_and_matches_requested_intent():
    payload = ConsultationCreate(
        question="请用 DCF 做估值",
        requested_intent="valuation_analysis",
        scene_input={
            "scene": "valuation_analysis",
            "currency": "CNY",
            "period": "FY2026",
            "dcf": {
                "free_cash_flows": [100, 110, 120],
                "wacc": 0.1,
                "terminal_growth": 0.03,
                "shares_outstanding": 100,
            },
        },
    )
    assert isinstance(payload.scene_input, ValuationAnalysisInput)


def test_scene_input_rejects_mismatched_requested_intent():
    with pytest.raises(ValidationError, match="requested_intent"):
        ConsultationCreate(
            question="请解释产品费用",
            requested_intent="product_explanation",
            scene_input={"scene": "valuation_analysis", "currency": "CNY", "period": "FY2026", "dcf": {"free_cash_flows": [1], "wacc": 0.1, "terminal_growth": 0.02, "shares_outstanding": 1}},
        )


def test_valuation_pipeline_uses_governed_finance_tool_and_preserves_provenance():
    payload = ConsultationCreate(
        question="请用 DCF 做估值",
        requested_intent="valuation_analysis",
        scene_input={
            "scene": "valuation_analysis",
            "currency": "CNY",
            "period": "FY2026",
            "dcf": {"free_cash_flows": [100, 110, 120], "wacc": 0.1, "terminal_growth": 0.03, "shares_outstanding": 100},
        },
    )
    case = ConsultationService(container).create(
        tenant_id="tenant-demo",
        user_id="dev-user",
        question=payload.question,
        requested_intent=payload.requested_intent,
        scene_input=payload.scene_input.model_dump(),
    )
    calculation = case.result["calculations"]["dcf_calculate"]
    assert case.status.value == "completed"
    assert calculation["formula_version"] == "dcf_v1.0.0"
    assert calculation["data_sources"] == ["user_supplied"]
    assert any(event["tool_id"] == "dcf_calculate" and event["pipeline_id"] == "valuation_analysis" for event in container.tool_gateway.execution_events)


def test_question_only_valuation_degrades_without_calculation():
    case = ConsultationService(container).create(
        tenant_id="tenant-demo",
        user_id="dev-user",
        question="请分析这家公司估值是否合理",
        requested_intent="valuation_analysis",
    )
    assert case.result["calculation_performed"] is False
    assert "valuation_inputs" in case.result["missing_fields"]

