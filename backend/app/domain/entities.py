"""咨询领域实体；实体字段保留租户、版本和审计所需的业务上下文。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.constants import ConsultationStatus, RiskLevel


def utcnow() -> datetime:
    """统一生成带时区的 UTC 时间，避免跨服务比较本地时间。"""
    return datetime.now(timezone.utc)


@dataclass
class Product:
    id: str
    tenant_id: str
    name: str
    product_type: str
    risk_level: RiskLevel
    fees: list[dict[str, Any]]
    liquidity: str
    description: str
    risk_disclosures: list[str]
    source_version: str
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    version: int = 1


@dataclass
class Document:
    id: str
    tenant_id: str
    title: str
    content: str
    sha256: str
    source: str
    authorization_scope: str = "tenant"
    object_version: str = "1"
    status: str = "ready"
    created_at: datetime = field(default_factory=utcnow)
    page_count: int | None = None
    section_path: str | None = None
    authorization_expires_at: datetime | None = None
    object_key: str | None = None


@dataclass
class ConsultationCase:
    id: str
    tenant_id: str
    user_id: str
    question: str
    intent: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    status: ConsultationStatus = ConsultationStatus.RECEIVED
    answer: str | None = None
    warnings: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    compliance: dict[str, Any] | None = None
    result: dict[str, Any] = field(default_factory=dict)
    risk_assessment: dict[str, Any] | None = None
    trace_id: str = field(default_factory=lambda: f"trace_{uuid4().hex}")
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)
    version: int = 1
    confirmation_required: bool = False
    confirmed_at: datetime | None = None
    expires_at: datetime | None = None
    scene_input: dict[str, Any] | None = None
    requested_intent: str | None = None
