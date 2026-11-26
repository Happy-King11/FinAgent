"""缓存接口的内存占位实现，不能作为唯一业务数据源。"""

from typing import Any


class Cache:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._values.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        # 当前实现忽略 TTL；生产适配器必须由 Redis 执行过期控制。
        self._values[key] = value


class RedisCache:
    """Redis 实现，支持 TTL 和跨进程幂等/任务状态。"""

    def __init__(self, client):
        self.client = client

    def get(self, key: str) -> Any | None:
        return self.client.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self.client.set(key, value, ex=ttl_seconds)
