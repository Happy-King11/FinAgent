"""租户隔离的进程内仓储，供 PoC 和单元测试使用。"""

from typing import Generic, TypeVar

from app.core.exceptions import NotFoundError

T = TypeVar("T")


class TenantMemoryRepository(Generic[T]):
    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def add(self, item: T, item_id: str) -> T:
        self._items[item_id] = item
        return item

    def get(self, item_id: str, tenant_id: str) -> T:
        # 找不到或租户不匹配统一返回 NOT_FOUND，避免泄露跨租户资源存在性。
        item = self._items.get(item_id)
        if item is None or getattr(item, "tenant_id", None) != tenant_id:
            raise NotFoundError()
        return item

    def list(self, tenant_id: str) -> list[T]:
        return [x for x in self._items.values() if getattr(x, "tenant_id", None) == tenant_id]


class ProductRepository(TenantMemoryRepository):
    def find_by_name(self, tenant_id: str, query: str) -> list:
        query = query.lower()
        return [p for p in self.list(tenant_id) if query in p.name.lower() or query in p.description.lower()]


class DocumentRepository(TenantMemoryRepository):
    pass


class ConsultationRepository(TenantMemoryRepository):
    pass
