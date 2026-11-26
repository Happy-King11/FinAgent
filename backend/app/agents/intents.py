"""Versioned intent definitions and deterministic routing policy."""

from dataclasses import dataclass
from enum import StrEnum


class RouteBand(StrEnum):
    DIRECT = "direct"
    CLARIFY = "clarify"
    HANDOFF = "handoff"


@dataclass(frozen=True)
class IntentDefinition:
    intent_id: str
    version: str
    keywords: tuple[str, ...]
    pipeline_ref: str
    risk_level: str = "low"
    requires_computation: bool = False
    requires_retrieval: bool = False
    requires_user_profile: bool = False
    requires_compliance_review: bool = True


class IntentRegistry:
    def __init__(self, definitions: tuple[IntentDefinition, ...] | None = None):
        self._items = {item.intent_id: item for item in (definitions or self.defaults())}

    @staticmethod
    def defaults() -> tuple[IntentDefinition, ...]:
        # The internal pilot exposes exactly eight business scenes.  Specific
        # multi-word phrases are preferred over a generic "risk" keyword so a
        # product-risk explanation does not get misrouted as a risk assessment.
        return (
            IntentDefinition(
                "single_stock_research",
                "1.0.0",
                ("单股", "个股", "股票", "公司研究", "基本面", "研究", "equity research", "single stock"),
                "single_stock_research@1.0.0",
                "medium",
                requires_computation=True,
                requires_retrieval=True,
            ),
            IntentDefinition(
                "product_explanation",
                "1.0.0",
                ("费用", "产品", "基金", "费率", "流动性", "说明书", "fee", "product", "fund"),
                "product_explanation@1.0.0",
                "low",
                requires_retrieval=True,
            ),
            IntentDefinition(
                "financial_knowledge",
                "1.0.0",
                ("什么是", "知识", "概念", "定义", "原理", "金融知识", "what is", "explain concept"),
                "financial_knowledge@1.0.0",
                "low",
                requires_retrieval=True,
            ),
            IntentDefinition(
                "portfolio_diagnosis",
                "1.0.0",
                ("组合", "持仓", "集中度", "行业暴露", "资产配置", "portfolio", "concentration"),
                "portfolio_diagnosis@1.0.0",
                "medium",
                requires_computation=True,
                requires_user_profile=True,
            ),
            IntentDefinition(
                "valuation_analysis",
                "1.0.0",
                ("估值", "DCF", "WACC", "可比公司", "内在价值", "折现率", "valuation"),
                "valuation_analysis@1.0.0",
                "medium",
                requires_computation=True,
                requires_retrieval=True,
            ),
            IntentDefinition(
                "financial_statement_analysis",
                "1.0.0",
                ("财报", "财务报表", "资产负债表", "利润表", "现金流量表", "营收", "净利润", "10-k", "filing"),
                "financial_statement_analysis@1.0.0",
                "medium",
                requires_computation=True,
                requires_retrieval=True,
            ),
            IntentDefinition(
                "risk_assessment",
                "1.0.0",
                ("风险评估", "风险测评", "风险诊断", "承受能力", "风险等级", "risk assessment", "risk profile"),
                "risk_assessment@1.0.0",
                "medium",
                requires_computation=True,
            ),
            IntentDefinition(
                "compliance_consultation",
                "1.0.0",
                ("合规", "监管", "适当性", "是否违规", "销售话术", "信息披露", "内幕", "保本", "保证收益", "compliance"),
                "compliance_consultation@1.0.0",
                "medium",
                requires_retrieval=True,
            ),
        )

    def get(self, intent_id: str) -> IntentDefinition:
        return self._items[intent_id]

    def all(self) -> tuple[IntentDefinition, ...]:
        return tuple(self._items.values())
