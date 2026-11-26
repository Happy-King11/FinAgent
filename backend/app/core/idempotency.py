"""Idempotency stores for single-process tests and shared Redis deployments."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from .exceptions import IdempotencyConflict


@dataclass
class IdempotencyRecord:
    request_hash: str
    response: Any


class IdempotencyStoreProtocol(Protocol):
    def get_or_raise(self, scope: str, key: str, payload: Any) -> Any | None: ...
    def put(self, scope: str, key: str, payload: Any, response: Any) -> None: ...


class IdempotencyStore:
    """Process-local test implementation; never use as production authority."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}

    @staticmethod
    def fingerprint(payload: Any) -> str:
        raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get_or_raise(self, scope: str, key: str, payload: Any) -> Any | None:
        record = self._records.get((scope, key))
        if record is None:
            return None
        if record.request_hash != self.fingerprint(payload):
            raise IdempotencyConflict()
        return record.response

    def put(self, scope: str, key: str, payload: Any, response: Any) -> None:
        self._records[(scope, key)] = IdempotencyRecord(self.fingerprint(payload), response)


class RedisIdempotencyStore:
    """Redis-backed store using one atomic create operation and a bounded TTL."""

    def __init__(self, client: Any, *, ttl_seconds: int = 86400, prefix: str = "financial-agent:idempotency") -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds
        self.prefix = prefix

    @staticmethod
    def _json_value(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return value

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(RedisIdempotencyStore._json_value(value), ensure_ascii=True, sort_keys=True, default=str)

    def _key(self, scope: str, key: str) -> str:
        return f"{self.prefix}:{scope}:{key}"

    def get_or_raise(self, scope: str, key: str, payload: Any) -> Any | None:
        raw = self.client.get(self._key(scope, key))
        if raw is None:
            return None
        record = json.loads(raw)
        if record["request_hash"] != IdempotencyStore.fingerprint(payload):
            raise IdempotencyConflict()
        return record["response"]

    def put(self, scope: str, key: str, payload: Any, response: Any) -> None:
        redis_key = self._key(scope, key)
        value = self._encode({"request_hash": IdempotencyStore.fingerprint(payload), "response": self._json_value(response)})
        # NX prevents a concurrent request from overwriting the first result.
        created = self.client.set(redis_key, value, ex=self.ttl_seconds, nx=True)
        if not created:
            existing = self.get_or_raise(scope, key, payload)
            if existing is None:
                raise RuntimeError("idempotency record disappeared during write")
