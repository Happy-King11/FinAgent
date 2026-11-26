"""OpenAI-compatible chat completion adapter."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _normalise_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("LLM base URL is required")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("LLM base URL must be an HTTP URL")
    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


@dataclass
class OpenAICompatibleClient:
    """Provider-neutral chat client with an injectable transport for tests."""

    base_url: str
    api_key: str
    model: str
    transport: Any | None = None
    max_tokens: int = 1200

    def __post_init__(self) -> None:
        self.base_url = _normalise_base_url(self.base_url)
        if not self.model.strip():
            raise ValueError("LLM model is required")
        if self.max_tokens <= 0:
            raise ValueError("LLM max tokens must be positive")

    def _request(self, prompt: str, *, model: str, timeout_seconds: int) -> Any:
        if self.transport is not None:
            return self.transport(
                prompt=prompt,
                model=model,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout_seconds=timeout_seconds,
            )
        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": self.max_tokens,
                },
                headers=headers,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider details stay behind this boundary.
            raise RuntimeError("LLM provider transport request failed") from exc

    def is_ready(self, *, timeout_seconds: int = 10) -> bool:
        """Check provider reachability without creating a completion."""
        if self.transport is not None:
            return True
        try:
            import httpx

            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = httpx.get(f"{self.base_url}/models", headers=headers, timeout=timeout_seconds)
            return response.is_success
        except Exception:  # noqa: BLE001 - readiness is intentionally boolean.
            return False

    def complete(self, prompt: str, *, model: str | None = None, timeout_seconds: int = 60) -> str:
        if not prompt.strip():
            raise ValueError("LLM prompt must not be empty")
        result = self._request(prompt, model=model or self.model, timeout_seconds=timeout_seconds)
        if not isinstance(result, dict):
            raise ValueError("LLM provider returned an invalid response")
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("LLM provider returned no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("LLM provider returned invalid message content")
        content = message["content"].strip()
        if not content:
            raise ValueError("LLM provider returned empty content")
        return content
