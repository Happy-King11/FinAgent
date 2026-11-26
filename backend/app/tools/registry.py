"""Validated tool manifests and registry."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolManifest:
    tool_id: str
    version: str = "1.0.0"
    risk_level: str = "L0"
    side_effect: str = "read_only"
    timeout_seconds: int = 5
    requires_confirmation: bool = False
    requires_approval: bool = False
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    cache_ttl_seconds: int | None = None
    fallback_tool_id: str | None = None
    required_data_entitlement: str | None = None

    def validate(self) -> None:
        if self.risk_level not in {"L0", "L1", "L2", "L3"}:
            raise ValueError("invalid tool risk level")
        if self.side_effect not in {"read_only", "write", "irreversible"}:
            raise ValueError("invalid tool side effect")
        if self.timeout_seconds <= 0:
            raise ValueError("tool timeout must be positive")
        if self.cache_ttl_seconds is not None and self.cache_ttl_seconds <= 0:
            raise ValueError("tool cache TTL must be positive")
        if self.risk_level == "L3" and not self.requires_approval:
            raise ValueError("L3 tools require approval")


class ToolRegistry:
    def __init__(self) -> None:
        self._items: dict[str, tuple[ToolManifest, Callable[..., Any]]] = {}

    def register(self, manifest: ToolManifest, handler: Callable[..., Any]) -> None:
        manifest.validate()
        if manifest.tool_id in self._items:
            raise ValueError(f"tool already registered: {manifest.tool_id}")
        self._items[manifest.tool_id] = (manifest, handler)

    def get(self, tool_id: str) -> tuple[ToolManifest, Callable[..., Any]]:
        return self._items[tool_id]
