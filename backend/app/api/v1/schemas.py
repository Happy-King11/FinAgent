"""API 请求和统一响应的 Pydantic schema。"""

from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, Field, field_validator
from pydantic import model_validator
from app.pipelines.types import ValuationAnalysisOutput

T = TypeVar("T")


class WarningItem(BaseModel):
    code: str = "WARNING"
    message: str


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    """所有业务响应的外层契约，避免各端点返回不同格式。"""

    request_id: str
    trace_id: str
    data: T | None = None
    warnings: list[WarningItem] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    compliance: dict[str, Any] | None = None
    error: ApiError | None = None


class SceneInputBase(BaseModel):
    """八场景输入的共同字段；scene 是判别联合的稳定标签。"""

    source_ids: list[str] = Field(default_factory=lambda: ["user_supplied"], min_length=1, max_length=20)

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, values: list[str]) -> list[str]:
        allowed = {"dev_fixture", "user_supplied", "authorized_document"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unsupported source_ids: {sorted(unknown)}")
        return values


class SingleStockResearchInput(SceneInputBase):
    scene: Literal["single_stock_research"] = "single_stock_research"
    security_id: str = Field(min_length=1, max_length=100)


class ProductExplanationInput(SceneInputBase):
    scene: Literal["product_explanation"] = "product_explanation"
    product_id: str | None = Field(default=None, max_length=100)


class FinancialKnowledgeInput(SceneInputBase):
    scene: Literal["financial_knowledge"] = "financial_knowledge"
    topic: str = Field(min_length=1, max_length=200)


class PortfolioDiagnosisInput(SceneInputBase):
    scene: Literal["portfolio_diagnosis"] = "portfolio_diagnosis"
    portfolio_ref: str = Field(min_length=1, max_length=100)
    confirmed_risk_profile: bool = False


class DCFInput(BaseModel):
    free_cash_flows: list[float] = Field(min_length=1, max_length=30)
    wacc: float
    terminal_growth: float
    net_debt: float = 0
    shares_outstanding: float = Field(gt=0)


class WACCInput(BaseModel):
    cost_of_equity: float
    cost_of_debt: float
    tax_rate: float = Field(ge=0, le=1)
    equity_value: float = Field(gt=0)
    debt_value: float = Field(ge=0)


class ComparableValuationInput(BaseModel):
    peer_multiples: list[float] = Field(min_length=1, max_length=100)
    target_metric: float = Field(gt=0)
    multiple_name: str = Field(default="pe", min_length=1, max_length=30)


class ScenarioInput(BaseModel):
    base_value: float
    scenarios: dict[str, float] = Field(min_length=1, max_length=20)


class ValuationAnalysisInput(SceneInputBase):
    scene: Literal["valuation_analysis"] = "valuation_analysis"
    currency: str = Field(min_length=3, max_length=10)
    period: str = Field(min_length=1, max_length=50)
    dcf: DCFInput | None = None
    wacc: WACCInput | None = None
    comparables: ComparableValuationInput | None = None
    scenario: ScenarioInput | None = None

    @model_validator(mode="after")
    def require_one_method(self):
        if not any((self.dcf, self.wacc, self.comparables, self.scenario)):
            raise ValueError("valuation input requires at least one calculation method")
        return self


class FinancialStatementAnalysisInput(SceneInputBase):
    scene: Literal["financial_statement_analysis"] = "financial_statement_analysis"
    security_id: str = Field(min_length=1, max_length=100)
    reporting_period: str = Field(min_length=1, max_length=50)


class RiskAssessmentInput(SceneInputBase):
    scene: Literal["risk_assessment"] = "risk_assessment"
    subject_type: Literal["user", "product", "security", "portfolio", "consultation"]


class ComplianceConsultationInput(SceneInputBase):
    scene: Literal["compliance_consultation"] = "compliance_consultation"
    rule_topic: str = Field(min_length=1, max_length=200)


SceneInput = Annotated[
    Union[
        SingleStockResearchInput,
        ProductExplanationInput,
        FinancialKnowledgeInput,
        PortfolioDiagnosisInput,
        ValuationAnalysisInput,
        FinancialStatementAnalysisInput,
        RiskAssessmentInput,
        ComplianceConsultationInput,
    ],
    Field(discriminator="scene"),
]


class ConsultationCreate(BaseModel):
    question: str = Field(min_length=1, max_length=10000)
    requested_intent: str | None = Field(default=None, max_length=60)
    scene_input: SceneInput | None = None

    @model_validator(mode="after")
    def validate_scene_alignment(self):
        if self.requested_intent and self.requested_intent not in {
            "single_stock_research", "product_explanation", "financial_knowledge", "portfolio_diagnosis",
            "valuation_analysis", "financial_statement_analysis", "risk_assessment", "compliance_consultation",
        }:
            raise ValueError("requested_intent is not one of the eight supported scenes")
        if self.scene_input and self.requested_intent and self.scene_input.scene != self.requested_intent:
            raise ValueError("requested_intent must match scene_input.scene")
        return self


class ConsultationMessage(BaseModel):
    question: str = Field(min_length=1, max_length=10000)


class ConfirmationRequest(BaseModel):
    confirmed: bool = True


class ProfileUpdate(BaseModel):
    risk_level: str = Field(pattern="^(low|medium|high)$")
    horizon_years: int = Field(ge=0, le=100)
    liquidity_need: str = Field(min_length=1, max_length=100)
    confirmed: bool = False


class SuitabilityRequest(BaseModel):
    product_risk_level: str = Field(pattern="^(low|medium|high)$")


class ReportRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=100)


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=2_000_000)
    source: str = "user_authorized"


class KnowledgeSearch(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


class RiskProfileInput(BaseModel):
    """组合诊断使用的已确认/待确认风险画像输入。"""

    risk_level: str = Field(pattern="^(low|medium|high)$")
    horizon_years: int = Field(ge=0, le=100)
    liquidity_need: str = Field(min_length=1, max_length=100)
    confirmed: bool = False


class PortfolioDiagnosisCreate(BaseModel):
    portfolio_id: str = Field(default="portfolio_demo", min_length=1, max_length=100)
    risk_profile: RiskProfileInput | None = None


class PortfolioReview(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(default="", max_length=2000)
