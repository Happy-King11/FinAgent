"""Tenant-scoped persistence for workflow records such as profiles and reports."""

from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from sqlalchemy import select

from app.core.exceptions import DomainError, NotFoundError
from app.infrastructure.database.models import DomainRecordModel
from app.infrastructure.database.session import set_tenant_context


class MemoryWorkflowRecordStore:
    """In-memory test substitute with the same tenant-scoped contract as SQL."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = RLock()

    def get(self, record_type: str, record_id: str, tenant_id: str) -> dict[str, Any]:
        record = self._records.get((record_type, record_id, tenant_id))
        if record is None:
            raise NotFoundError()
        return dict(record)

    def find(self, record_type: str, record_id: str, tenant_id: str) -> dict[str, Any] | None:
        try:
            return self.get(record_type, record_id, tenant_id)
        except NotFoundError:
            return None

    def put(self, record_type: str, record_id: str, tenant_id: str, payload: dict[str, Any], *, expected_version: int | None = None) -> dict[str, Any]:
        with self._lock:
            value = dict(payload)
            current = self._records.get((record_type, record_id, tenant_id))
            if current is not None and expected_version is not None and int(current.get("version", 1)) != expected_version:
                raise DomainError("STALE_DATA", "workflow record version is stale", 409)
            if current is None and expected_version not in (None, 0):
                raise DomainError("STALE_DATA", "workflow record version is stale", 409)
            value.update(id=record_id, tenant_id=tenant_id, record_type=record_type)
            value["version"] = int(current.get("version", 0)) + 1 if current else int(value.get("version", 1))
            self._records[(record_type, record_id, tenant_id)] = value
            return dict(value)


class SQLWorkflowRecordStore:
    """Small repository over domain_records for workflow data without ORM leakage."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self.session_factory = session_factory

    def get(self, record_type: str, record_id: str, tenant_id: str) -> dict[str, Any]:
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            row = session.scalar(
                select(DomainRecordModel).where(
                    DomainRecordModel.id == record_id,
                    DomainRecordModel.tenant_id == tenant_id,
                    DomainRecordModel.record_type == record_type,
                )
            )
            if row is None:
                raise NotFoundError()
            value = dict(row.payload or {})
            value.update(id=row.id, tenant_id=row.tenant_id, record_type=row.record_type, version=row.version)
            return value

    def find(self, record_type: str, record_id: str, tenant_id: str) -> dict[str, Any] | None:
        try:
            return self.get(record_type, record_id, tenant_id)
        except NotFoundError:
            return None

    def put(self, record_type: str, record_id: str, tenant_id: str, payload: dict[str, Any], *, expected_version: int | None = None) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            row = session.scalar(
                select(DomainRecordModel).where(
                    DomainRecordModel.id == record_id,
                    DomainRecordModel.tenant_id == tenant_id,
                    DomainRecordModel.record_type == record_type,
                ).with_for_update()
            )
            if row is None:
                if expected_version not in (None, 0):
                    raise DomainError("STALE_DATA", "workflow record version is stale", 409)
                row = DomainRecordModel(
                    id=record_id,
                    tenant_id=tenant_id,
                    record_type=record_type,
                    version=1,
                    payload=dict(payload),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                if expected_version is not None and row.version != expected_version:
                    raise DomainError("STALE_DATA", "workflow record version is stale", 409)
                row.payload = dict(payload)
                row.version += 1
                row.updated_at = now
            session.commit()
            value = dict(row.payload or {})
            value.update(id=row.id, tenant_id=row.tenant_id, record_type=row.record_type, version=row.version)
            return value
