"""LLM Provider 最小协议；业务层不依赖具体模型厂商 SDK。"""

from typing import Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str, *, model: str | None = None, timeout_seconds: int = 60) -> str: ...
