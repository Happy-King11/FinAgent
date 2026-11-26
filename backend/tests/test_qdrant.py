"""Qdrant adapter contract tests using a small fake client."""

from types import SimpleNamespace

import pytest

from app.infrastructure.vector_store.qdrant import QdrantVectorStore


class FakeQdrant:
    def __init__(self, *, exists=False, size=3, distance="Cosine"):
        self.points = []
        self.created = False
        self.exists = exists
        self.info = SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(size=size, distance=distance)))

    def get_collection(self, _collection):
        if not self.exists and not self.created:
            raise RuntimeError("collection not found")
        return self.info

    def create_collection(self, **_kwargs):
        self.created = True

    def upsert(self, *, points, **_kwargs):
        self.points = points

    def search(self, **_kwargs):
        return [SimpleNamespace(payload=self.points[0].payload, score=0.9)] if self.points else []

    def delete(self, **_kwargs):
        self.points = []


def make_store(fake):
    store = object.__new__(QdrantVectorStore)
    store._models = SimpleNamespace(
        PointStruct=lambda **kwargs: SimpleNamespace(**kwargs),
        VectorParams=lambda **kwargs: SimpleNamespace(**kwargs),
        Distance=SimpleNamespace(COSINE="Cosine"),
        Filter=lambda **kwargs: SimpleNamespace(**kwargs),
        FieldCondition=lambda **kwargs: SimpleNamespace(**kwargs),
        MatchValue=lambda **kwargs: SimpleNamespace(**kwargs),
        FilterSelector=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    store.collection = "documents"
    store.dimension = 3
    store.client = fake
    return store


def test_qdrant_upsert_uses_stable_point_and_payload_scope():
    fake = FakeQdrant()
    store = make_store(fake)
    store.upsert(document_id="doc-1", tenant_id="tenant-a", text="cash", embedding=[1, 0, 0], metadata={"status": "ready"})
    point_id = fake.points[0].id
    store.upsert(document_id="doc-1", tenant_id="tenant-a", text="cash", embedding=[1, 0, 0], metadata={"status": "ready"})
    assert fake.points[0].id == point_id
    assert fake.points[0].payload["tenant_id"] == "tenant-a"
    assert fake.points[0].payload["authorization_expired"] is False


def test_qdrant_search_returns_payload_document():
    fake = FakeQdrant()
    store = make_store(fake)
    store.upsert(document_id="doc-1", tenant_id="tenant-a", text="cash", embedding=[1, 0, 0], metadata={"status": "ready"})
    result = store.search(tenant_id="tenant-a", query="cash", embedding=[1, 0, 0], limit=1)
    assert result[0]["document_id"] == "doc-1"
    assert result[0]["tenant_id"] == "tenant-a"


def test_qdrant_rejects_dimension_mismatch():
    store = make_store(FakeQdrant())
    with pytest.raises(ValueError, match="dimension"):
        store.upsert(document_id="doc-1", tenant_id="tenant-a", text="cash", embedding=[1, 0], metadata={})
