"""Qdrant adapter with payload-level tenant and authorization filtering."""

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5


class QdrantVectorStore:
    def __init__(self, url: str, collection: str, dimension: int, api_key: str = "", timeout: float = 10) -> None:
        if not collection.strip():
            raise ValueError("Qdrant collection is required")
        if dimension <= 0:
            raise ValueError("Qdrant vector dimension must be positive")
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
        except ImportError as exc:
            raise RuntimeError("qdrant-client is not installed") from exc
        self._models = models
        self.collection = collection
        self.dimension = dimension
        self.client = QdrantClient(url=url, api_key=api_key or None, timeout=timeout)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        models = self._models
        try:
            info = self.client.get_collection(self.collection)
        except Exception as exc:  # noqa: BLE001 - adapter normalizes dependency failures.
            if not self._is_missing_collection(exc):
                raise RuntimeError("Qdrant collection check failed") from exc
            try:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=models.VectorParams(size=self.dimension, distance=models.Distance.COSINE),
                )
                return
            except Exception as create_exc:  # noqa: BLE001
                raise RuntimeError("Qdrant collection creation failed") from create_exc
        configured = getattr(getattr(info, "config", None), "params", None)
        vectors = getattr(configured, "vectors", configured)
        if isinstance(vectors, dict):
            vectors = vectors.get("") or vectors.get("default")
        size = getattr(vectors, "size", None)
        distance = getattr(vectors, "distance", None)
        distance_name = getattr(distance, "value", distance)
        if size != self.dimension or str(distance_name).lower().split(".")[-1] != "cosine":
            raise ValueError("Qdrant collection vector schema does not match configuration")

    @staticmethod
    def _is_missing_collection(exc: Exception) -> bool:
        return "not found" in str(exc).lower() or "doesn't exist" in str(exc).lower()

    def _point_id(self, tenant_id: str, document_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"financial-agent:{tenant_id}:{document_id}"))

    @staticmethod
    def _expired(metadata: dict[str, Any]) -> bool:
        value = metadata.get("authorization_expires_at")
        if not value:
            return bool(metadata.get("authorization_expired", False))
        try:
            expires = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            return expires <= datetime.now(timezone.utc)
        except ValueError:
            return True

    def upsert(self, *, document_id: str, tenant_id: str, text: str, metadata: dict, embedding: list[float] | None = None) -> None:
        if not tenant_id or not document_id or not embedding:
            raise ValueError("tenant, document and embedding are required")
        if len(embedding) != self.dimension:
            raise ValueError("embedding dimension does not match Qdrant collection")
        payload = dict(metadata)
        payload.update({"tenant_id": tenant_id, "document_id": document_id, "text": text})
        payload["authorization_expired"] = self._expired(payload)
        try:
            self.client.upsert(
                collection_name=self.collection,
                points=[self._models.PointStruct(id=self._point_id(tenant_id, document_id), vector=embedding, payload=payload)],
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Qdrant upsert failed") from exc

    def search(self, *, tenant_id: str, query: str, limit: int = 5, embedding: list[float] | None = None) -> list[dict]:
        if limit <= 0 or not embedding:
            return []
        if len(embedding) != self.dimension:
            raise ValueError("embedding dimension does not match Qdrant collection")
        models = self._models
        tenant_filter = models.Filter(
            must=[
                models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
                models.FieldCondition(key="status", match=models.MatchValue(value="ready")),
            ],
            must_not=[models.FieldCondition(key="authorization_expired", match=models.MatchValue(value=True))],
        )
        try:
            points = self.client.search(
                collection_name=self.collection,
                query_vector=embedding,
                query_filter=tenant_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Qdrant search failed") from exc
        results = []
        for point in points:
            payload = dict(point.payload or {})
            results.append({
                "document_id": payload.get("document_id", ""),
                "tenant_id": payload.get("tenant_id", tenant_id),
                "text": payload.get("text", ""),
                "metadata": {key: value for key, value in payload.items() if key not in {"document_id", "tenant_id", "text"}},
                "score": getattr(point, "score", 0.0),
            })
        return results

    def delete_tenant(self, tenant_id: str) -> None:
        if not tenant_id:
            raise ValueError("tenant is required")
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=self._models.FilterSelector(
                    filter=self._models.Filter(must=[self._models.FieldCondition(key="tenant_id", match=self._models.MatchValue(value=tenant_id))])
                ),
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Qdrant tenant deletion failed") from exc

    def is_ready(self) -> bool:
        try:
            self.client.get_collection(self.collection)
            return True
        except Exception:  # noqa: BLE001
            return False
