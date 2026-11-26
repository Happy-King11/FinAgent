"""工具执行网关：在调用注册函数前执行合规、权限和契约检查。"""

from dataclasses import dataclass, field
from hashlib import sha256
import json
import time
from typing import Any, Callable

from app.core.exceptions import DomainError
from app.tools.compliance import ComplianceEngine
from app.tools.reliability import CircuitBreaker, call_with_retry
from app.tools.registry import ToolManifest, ToolRegistry


@dataclass(frozen=True)
class ToolExecutionContext:
    """调用工具所需的租户、确认和审批上下文。"""

    tenant_id: str
    user_id: str | None = None
    confirmed: bool = False
    approved: bool = False
    data_entitlements: frozenset[str] = field(default_factory=frozenset)
    allowed_tools: frozenset[str] | None = None
    blocked_tools: frozenset[str] = field(default_factory=frozenset)
    case_id: str | None = None
    trace_id: str | None = None
    pipeline_id: str | None = None
    pipeline_version: str | None = None

    def allows(self, entitlement: str | None) -> bool:
        return entitlement is None or "*" in self.data_entitlements or entitlement in self.data_entitlements

    def allows_tool(self, tool_id: str) -> bool:
        if tool_id in self.blocked_tools:
            return False
        return self.allowed_tools is None or tool_id in self.allowed_tools


def _validate_schema(value: Any, schema: dict[str, Any] | None, *, label: str) -> None:
    """Validate the small JSON-schema subset used by tool manifests."""
    if schema is None:
        return
    expected = schema.get("type")
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, (list, tuple)),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected not in type_checks:
        raise DomainError("TOOL_CONTRACT_INVALID", f"unsupported {label} schema type", 500)
    if not type_checks[expected](value):
        raise DomainError("TOOL_CONTRACT_VIOLATION", f"tool {label} does not match its contract", 422)
    if expected != "object":
        return
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
        raise DomainError("TOOL_CONTRACT_INVALID", f"invalid required fields in {label} schema", 500)
    missing = [key for key in required if key not in value]
    if missing:
        raise DomainError("TOOL_CONTRACT_VIOLATION", f"tool {label} is missing required fields", 422)
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        raise DomainError("TOOL_CONTRACT_INVALID", f"invalid properties in {label} schema", 500)
    for key, property_schema in properties.items():
        if key in value:
            _validate_schema(value[key], property_schema, label=f"{label}.{key}")


class ToolGateway:
    def __init__(self, compliance: ComplianceEngine | None = None) -> None:
        self.compliance = compliance or ComplianceEngine()
        self._tools: dict[str, Callable[..., Any]] = {}
        self._manifests: dict[str, ToolManifest] = {}
        self._registry = ToolRegistry()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._cache: dict[str, tuple[float, Any]] = {}
        self.execution_events: list[dict[str, Any]] = []

    def register(self, tool_id: str, fn: Callable[..., Any], manifest: ToolManifest | None = None) -> None:
        selected = manifest or ToolManifest(tool_id=tool_id)
        if selected.tool_id != tool_id:
            raise ValueError("tool manifest id must match the registered tool id")
        selected.validate()
        self._tools[tool_id] = fn
        self._manifests[tool_id] = selected
        self._registry.register(selected, fn)

    def execute(self, tool_id: str, *, input_text: str = "", context: ToolExecutionContext | None = None, **kwargs: Any) -> Any:
        # 所有外部工具都必须经过网关，业务层不能直接调用工具函数。
        return self._execute(tool_id, input_text=input_text, context=context, visited=set(), **kwargs)

    def _execute(self, tool_id: str, *, input_text: str, context: ToolExecutionContext | None, visited: set[str], **kwargs: Any) -> Any:
        started_at = time.time()
        self._record_execution("started", tool_id, context, kwargs, started_at=started_at)
        decision = self.compliance.check(input_text)
        if decision.decision == "block":
            self._record_execution("blocked", tool_id, context, kwargs, started_at=started_at)
            raise DomainError("COMPLIANCE_BLOCKED", decision.reason or "tool call blocked", 422)
        tool = self._tools.get(tool_id)
        if tool is None:
            self._record_execution("unavailable", tool_id, context, kwargs, started_at=started_at)
            raise DomainError("TOOL_UNAVAILABLE", f"tool {tool_id} is not registered", 503)
        manifest = self._manifests[tool_id]
        if context is not None and not context.allows_tool(tool_id):
            self._record_execution("not_allowed", tool_id, context, kwargs, started_at=started_at)
            raise DomainError("TOOL_NOT_ALLOWED", f"tool {tool_id} is not allowed by the active pipeline", 403)
        if context is not None and "tenant_id" in kwargs and kwargs["tenant_id"] != context.tenant_id:
            raise DomainError("TENANT_SCOPE_VIOLATION", "tool tenant does not match execution context", 403)
        if context is not None and not context.allows(manifest.required_data_entitlement):
            raise DomainError("DATA_ENTITLEMENT_DENIED", "data entitlement is required before tool execution", 403)
        if manifest.requires_confirmation and not (context and context.confirmed):
            raise DomainError("CONFIRMATION_REQUIRED", "tool confirmation is required before execution", 409)
        if manifest.requires_approval and not (context and context.approved):
            raise DomainError("PERMISSION_DENIED", "tool approval is required before execution", 403)
        _validate_schema(kwargs, manifest.input_schema, label="input")
        cache_key = self._cache_key(tool_id, input_text, context, kwargs)
        if manifest.cache_ttl_seconds:
            cached = self._cache.get(cache_key)
            if cached and cached[0] > time.monotonic():
                self._record_execution("cache_hit", tool_id, context, kwargs, started_at=started_at)
                return cached[1]
        try:
            result = call_with_retry(
                tool,
                attempts=2,
                timeout_seconds=manifest.timeout_seconds,
                breaker=self._breakers.setdefault(tool_id, CircuitBreaker()),
                idempotent=manifest.side_effect == "read_only",
                **kwargs,
            )
        except DomainError:
            raise
        except Exception:
            if not manifest.fallback_tool_id or tool_id in visited:
                self._record_execution("failed", tool_id, context, kwargs, started_at=started_at)
                raise
            visited.add(tool_id)
            self._record_execution("fallback", tool_id, context, kwargs, started_at=started_at)
            return self._execute(manifest.fallback_tool_id, input_text=input_text, context=context, visited=visited, **kwargs)
        _validate_schema(result, manifest.output_schema, label="output")
        if manifest.cache_ttl_seconds:
            self._cache[cache_key] = (time.monotonic() + manifest.cache_ttl_seconds, result)
        self._record_execution("succeeded", tool_id, context, kwargs, started_at=started_at)
        return result

    def _record_execution(self, status: str, tool_id: str, context: ToolExecutionContext | None, kwargs: dict[str, Any], *, started_at: float) -> None:
        """保存脱敏工具调用摘要；不记录原始 prompt、密钥或持仓明细。"""
        self.execution_events.append({
            "status": status,
            "tool_id": tool_id,
            "tenant_id": context.tenant_id if context else kwargs.get("tenant_id"),
            "case_id": context.case_id if context else None,
            "trace_id": context.trace_id if context else None,
            "pipeline_id": context.pipeline_id if context else None,
            "pipeline_version": context.pipeline_version if context else None,
            "input_hash": sha256(json.dumps(kwargs, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
            "started_at": started_at,
            "finished_at": time.time(),
        })

    @staticmethod
    def _cache_key(tool_id: str, input_text: str, context: ToolExecutionContext | None, kwargs: dict[str, Any]) -> str:
        payload = {
            "tool_id": tool_id,
            "input_text": input_text,
            "tenant_id": context.tenant_id if context else kwargs.get("tenant_id"),
            "kwargs": kwargs,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()
