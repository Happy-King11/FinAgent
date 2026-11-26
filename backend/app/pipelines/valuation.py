"""估值 Pipeline：只消费结构化输入并通过 ToolGateway 调用确定性引擎。"""

from typing import Any

from app.pipelines.types import PipelineOutput, ValuationAnalysisOutput
from app.tools.gateway import ToolExecutionContext, ToolGateway


class ValuationPipeline:
    """编排 DCF/WACC/Comps/Scenario，不生成或改写任何估值数字。"""

    def run(self, scene_input: dict[str, Any] | None, gateway: ToolGateway, context: ToolExecutionContext) -> PipelineOutput:
        # question-only valuation requests remain safe and explain missing inputs.
        if not scene_input:
            output = ValuationAnalysisOutput(
                calculation_performed=False,
                missing_fields=["valuation_inputs"],
                warnings=["请提供 DCF/WACC/可比公司等结构化参数及来源。"],
            )
            return PipelineOutput(
                facts="当前估值咨询缺少结构化输入，未执行估值计算。",
                warnings=("请提供 DCF/WACC/可比公司等结构化参数及来源。",),
                missing_fields=("valuation_inputs",),
                result=output.model_dump(),
            )
        source_ids = tuple(scene_input.get("source_ids") or ("user_supplied",))
        currency = scene_input["currency"]
        period = scene_input["period"]
        calculations: dict[str, dict[str, Any]] = {}
        missing: list[str] = []

        if scene_input.get("wacc"):
            payload = {**scene_input["wacc"], "currency": currency, "period": period, "data_sources": list(source_ids)}
            calculations["wacc_calculate"] = gateway.execute("wacc_calculate", context=context, **payload)
        if scene_input.get("dcf"):
            payload = {**scene_input["dcf"], "currency": currency, "period": period, "data_sources": list(source_ids)}
            calculations["dcf_calculate"] = gateway.execute("dcf_calculate", context=context, **payload)
        if scene_input.get("comparables"):
            payload = {**scene_input["comparables"], "currency": currency, "period": period, "data_sources": list(source_ids)}
            calculations["comparable_valuation"] = gateway.execute("comparable_valuation", context=context, **payload)
        if scene_input.get("scenario"):
            payload = {**scene_input["scenario"], "currency": currency, "period": period, "data_sources": list(source_ids)}
            calculations["scenario_calculate"] = gateway.execute("scenario_calculate", context=context, **payload)

        if not calculations:
            missing.append("valuation_inputs")
        completed = [name for name, result in calculations.items() if result.get("status") == "completed"]
        facts = "；".join(
            f"{name}: {result.get('value')}（公式 {result.get('formula_version')}，来源 {','.join(result.get('data_sources', source_ids))}）"
            for name, result in calculations.items()
        ) or "未执行估值计算。"
        warnings = tuple(
            warning
            for result in calculations.values()
            for warning in result.get("warnings", [])
        )
        if not completed:
            missing.extend(field for result in calculations.values() for field in result.get("missing_fields", []))
        output = ValuationAnalysisOutput(
            calculation_performed=bool(calculations),
            calculations=calculations,
            missing_fields=sorted(set(missing)),
            warnings=list(warnings),
        )
        return PipelineOutput(
            facts=facts,
            warnings=warnings,
            missing_fields=tuple(sorted(set(missing))),
            result=output.model_dump(),
        )
