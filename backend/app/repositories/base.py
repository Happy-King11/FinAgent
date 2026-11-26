"""仓储最小协议，所有查询接口都显式接收 tenant_id。"""

from typing import Protocol, TypeVar

T = TypeVar("T")


class Repository(Protocol[T]):
    def get(self, item_id: str, tenant_id: str) -> T: ...

    def list(self, tenant_id: str) -> list[T]: ...
