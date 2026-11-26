"""Shared structured output for the eight consultation pipelines."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from typing import Literal


@dataclass(frozen=True)
class PipelineOutput:
    facts: str
    citations: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    result: dict[str, Any] = field(default_factory=dict)


class ValuationAnalysisOutput(BaseModel):
    """估值 Pipeline 输出；数字必须来自工具返回的 FinanceResult。"""

    scene: Literal["valuation_analysis"] = "valuation_analysis"
    calculation_performed: bool
    calculations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)

