"""Rebuildable tenant-filtered vector storage with cosine similarity."""

import math
from typing import Any


class MemoryVectorStore:
    def __init__(self):
        self._items: dict[tuple[str, str], dict[str, Any]] = {}

    def upsert(self, *, document_id: str, tenant_id: str, text: str, metadata: dict, embedding: list[float] | None = None) -> None:
        self._items[(tenant_id, document_id)] = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "text": text,
            "metadata": dict(metadata),
            "embedding": list(embedding or []),
        }

    def delete_tenant(self, tenant_id: str) -> None:
        self._items = {key: item for key, item in self._items.items() if key[0] != tenant_id}

    def is_ready(self) -> bool:
        return True

    def search(self, *, tenant_id: str, query: str, limit: int = 5, embedding: list[float] | None = None) -> list[dict]:
        if limit <= 0:
            return []
        candidates = [
            item
            for (item_tenant, _), item in self._items.items()
            if item_tenant == tenant_id
            and item["metadata"].get("status", "ready") == "ready"
            and not item["metadata"].get("authorization_expired", False)
        ]
        if embedding:
            ranked = [(self._cosine(embedding, item["embedding"]), item) for item in candidates if item["embedding"]]
            ranked.sort(key=lambda pair: pair[0], reverse=True)
            vector_results = [item for score, item in ranked if score > 0][:limit]
            if vector_results:
                return vector_results
            # Keep the memory test double useful for CJK substring queries when
            # hashing tokens do not share whitespace boundaries.
        terms = [term.lower() for term in query.split() if len(term) > 1]
        ranked = [(sum(term in item["text"].lower() for term in terms), item) for item in candidates]
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [item for score, item in ranked if score][:limit]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return 0.0
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)
