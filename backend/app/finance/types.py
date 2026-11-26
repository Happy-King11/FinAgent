"""统一、可回放的确定性金融计算结果。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class FinanceResult:
    status: str
    metric: str
    value: Decimal | None
    formula_version: str
    assumptions: dict[str, Any] = field(default_factory=dict)
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    calculated_at: str = ""
    currency: str | None = None
    unit: str | None = None
    period: str | None = None
    data_sources: tuple[str, ...] = ()
    confidence: str | None = None

    def __post_init__(self):
        if self.value is not None and not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))
        if not self.calculated_at:
            object.__setattr__(self, "calculated_at", datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        result = self.__dict__.copy()
        if isinstance(result["value"], Decimal):
            result["value"] = str(result["value"])
        result["data_sources"] = list(self.data_sources)
        result["missing_fields"] = list(self.missing_fields)
        result["warnings"] = list(self.warnings)
        return result


def decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return None
    return result if result.is_finite() else None
