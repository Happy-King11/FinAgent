"""Embedding provider abstractions with a credential-free local fallback."""

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class HashingEmbedding:
    """Deterministic local embedding for development; not a semantic model."""

    dimension: int = 64

    def embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimension
        tokens = text.lower().split()
        if not tokens:
            return values
        for index, token in enumerate(tokens):
            digest = hashlib.sha256(f"{index}:{token}".encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            values[bucket] += sign
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values] if norm else values


def _normalise_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("embedding base URL is required")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("embedding base URL must be an HTTP URL")
    path = parts.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


@dataclass
class OpenAICompatibleEmbedding:
    """Adapter for providers exposing an OpenAI-compatible embeddings API."""

    base_url: str
    api_key: str
    model: str
    dimension: int = 0
    timeout_seconds: float = 60
    transport: Any | None = None

    def __post_init__(self) -> None:
        self.base_url = _normalise_base_url(self.base_url)
        if not self.model.strip():
            raise ValueError("embedding model is required")
        if self.timeout_seconds <= 0:
            raise ValueError("embedding timeout must be positive")

    def _request(self, *, input_text: str | list[str]) -> Any:
        if self.transport is not None:
            return self.transport(
                input=input_text,
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
            )
        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = httpx.post(
                f"{self.base_url}/embeddings",
                json={"input": input_text, "model": self.model},
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - hide provider internals at the adapter boundary.
            raise RuntimeError("embedding provider transport request failed") from exc

    def _parse_vectors(self, result: Any, expected_count: int) -> list[list[float]]:
        if not isinstance(result, dict):
            raise ValueError("embedding provider returned an invalid response")
        if result.get("model") and result["model"] != self.model:
            raise ValueError("embedding provider returned an unexpected model")
        data = result.get("data")
        if not isinstance(data, list) or len(data) != expected_count:
            raise ValueError("embedding provider returned an invalid response")
        ordered: list[tuple[int, list[float]]] = []
        for position, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError("embedding provider returned an invalid response")
            raw_vector = item.get("embedding")
            if not isinstance(raw_vector, list) or not raw_vector:
                raise ValueError("embedding provider returned an empty vector")
            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError) as exc:
                raise ValueError("embedding provider returned an invalid vector") from exc
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("embedding provider returned a non-finite vector")
            if self.dimension and len(vector) != self.dimension:
                raise ValueError("embedding dimension does not match provider configuration")
            index = item.get("index", position)
            if not isinstance(index, int) or index < 0:
                raise ValueError("embedding provider returned an invalid index")
            ordered.append((index, vector))
        ordered.sort(key=lambda pair: pair[0])
        if [index for index, _ in ordered] != list(range(expected_count)):
            raise ValueError("embedding provider returned invalid indexes")
        return [vector for _, vector in ordered]

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("embedding input must not be empty")
        return self._parse_vectors(self._request(input_text=text), 1)[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedding input must not be empty")
        if len(texts) > 512:
            raise ValueError("embedding batch is too large")
        return self._parse_vectors(self._request(input_text=texts), len(texts))
