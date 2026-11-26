"""Typed SQL repositories for local and production persistence wiring."""

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from sqlalchemy import select, update

from app.core.exceptions import NotFoundError
from app.core.constants import ConsultationStatus, RiskLevel
from app.domain.entities import ConsultationCase, Document, Product
from app.infrastructure.database.models import ConsultationCaseModel, DocumentModel, ProductModel
from app.infrastructure.database.session import set_tenant_context

T = TypeVar("T")


def _payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        result = asdict(value)
    elif hasattr(value, "model_dump"):
        result = value.model_dump()
    else:
        result = dict(value)
    return _json_safe(result)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class SQLRepository(Generic[T]):
    """Tenant-scoped repository for one SQLAlchemy model and domain converter."""

    def __init__(self, session_factory: Callable[[], Any], model: Any, converter: Callable[[Any], T]):
        self.session_factory = session_factory
        self.model = model
        self.converter = converter

    def add(self, item: T, item_id: str | None = None) -> T:
        payload = _payload(item)
        identifier = item_id or str(payload["id"])
        now = datetime.now(timezone.utc)
        columns = {column.name for column in self.model.__table__.columns}
        values = {key: value for key, value in payload.items() if key in columns}
        if "created_at" in columns:
            values["created_at"] = values.get("created_at", now)
        if "updated_at" in columns:
            values["updated_at"] = values.get("updated_at", now)
        values.update(id=identifier, tenant_id=payload["tenant_id"])
        with self.session_factory() as session:
            set_tenant_context(session, str(payload["tenant_id"]))
            existing = session.scalar(select(self.model).where(self.model.id == identifier, self.model.tenant_id == payload["tenant_id"]))
            if existing is not None:
                changes = {key: value for key, value in values.items() if key not in {"id", "tenant_id", "created_at"}}
                if changes:
                    session.execute(update(self.model).where(self.model.id == identifier, self.model.tenant_id == payload["tenant_id"]).values(**changes))
                    session.commit()
                return item
            session.add(self.model(**values))
            session.commit()
        return item

    def get(self, item_id: str, tenant_id: str) -> T:
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            row = session.scalar(select(self.model).where(self.model.id == item_id, self.model.tenant_id == tenant_id))
            if row is None:
                raise NotFoundError()
            return self.converter(row)

    def list(self, tenant_id: str) -> list[T]:
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            rows = session.scalars(select(self.model).where(self.model.tenant_id == tenant_id)).all()
            return [self.converter(row) for row in rows]


class SQLProductRepository(SQLRepository[Product]):
    def __init__(self, session_factory: Callable[[], Any]):
        super().__init__(session_factory, ProductModel, self._convert)

    @staticmethod
    def _convert(row: ProductModel) -> Product:
        from app.core.constants import RiskLevel

        return Product(row.id, row.tenant_id, row.name, row.product_type, RiskLevel(row.risk_level), row.fees or [], row.liquidity, row.description, row.risk_disclosures or [], row.source_version, row.created_at, row.updated_at, row.version)

    def find_by_name(self, tenant_id: str, query: str) -> list[Product]:
        query = query.lower()
        return [item for item in self.list(tenant_id) if query in item.name.lower() or query in item.description.lower()]


class SQLDocumentRepository(SQLRepository[Document]):
    def __init__(self, session_factory: Callable[[], Any]):
        super().__init__(session_factory, DocumentModel, self._convert)

    @staticmethod
    def _convert(row: DocumentModel) -> Document:
        return Document(row.id, row.tenant_id, row.title, row.content or "", row.sha256, row.source, row.authorization_scope, row.object_version, row.status, row.created_at, row.page_count, None, row.authorization_expires_at, row.object_key)


class SQLConsultationRepository(SQLRepository[ConsultationCase]):
    def __init__(self, session_factory: Callable[[], Any]):
        super().__init__(session_factory, ConsultationCaseModel, self._convert)

    @staticmethod
    def _convert(row: ConsultationCaseModel) -> ConsultationCase:
        return ConsultationCase(
            id=row.id,
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            question=row.question,
            intent=row.intent,
            requested_intent=getattr(row, "requested_intent", None),
            scene_input=getattr(row, "scene_input", None),
            risk_level=RiskLevel(row.risk_level),
            status=ConsultationStatus(row.status),
            answer=row.answer,
            warnings=row.warnings or [],
            citations=row.citations or [],
            compliance=row.compliance,
            result=getattr(row, "result", None) or {},
            risk_assessment=getattr(row, "risk_assessment", None),
            trace_id=row.trace_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
            confirmation_required=getattr(row, "confirmation_required", False),
            confirmed_at=getattr(row, "confirmed_at", None),
            expires_at=getattr(row, "expires_at", None),
        )
