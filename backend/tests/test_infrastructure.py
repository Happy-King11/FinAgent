"""Infrastructure adapter tests that do not require external services."""

import pytest

from app.application.document_indexing import DocumentIndexer
from app.core.idempotency import RedisIdempotencyStore
from app.domain.entities import Document
from app.infrastructure.object_storage.s3 import S3ObjectStorage
from app.infrastructure.vector_store.memory import MemoryVectorStore
from app.llm.embeddings import HashingEmbedding, OpenAICompatibleEmbedding


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, *, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True


def test_redis_idempotency_replays_and_detects_conflicts():
    store = RedisIdempotencyStore(FakeRedis(), ttl_seconds=60)
    payload = {"question": "product fees"}
    response = {"request_id": "req-1", "data": {"status": "completed"}}

    store.put("tenant-a:user-a", "request-1", payload, response)
    assert store.get_or_raise("tenant-a:user-a", "request-1", payload) == response

    try:
        store.get_or_raise("tenant-a:user-a", "request-1", {"question": "different"})
    except Exception as exc:
        assert exc.code == "IDEMPOTENCY_CONFLICT"
    else:
        raise AssertionError("a changed payload must conflict")


def test_hashing_embedding_is_deterministic_and_normalized():
    provider = HashingEmbedding(16)
    first = provider.embed("cash flow risk")
    assert first == provider.embed("cash flow risk")
    assert len(first) == 16
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_embedding_adapter_accepts_openai_compatible_response():
    provider = OpenAICompatibleEmbedding(
        "https://embedding.invalid",
        "runtime-key",
        "embed-model",
        transport=lambda **_: {"data": [{"embedding": [1, 0]}]},
    )
    assert provider.embed("text") == [1.0, 0.0]


def test_vector_store_hard_filters_tenant_and_supports_embedding_search():
    store = MemoryVectorStore()
    store.upsert(document_id="a", tenant_id="tenant-a", text="cash flow", embedding=[1, 0], metadata={"status": "ready"})
    store.upsert(document_id="b", tenant_id="tenant-b", text="cash flow", embedding=[1, 0], metadata={"status": "ready"})
    assert [item["document_id"] for item in store.search(tenant_id="tenant-a", query="ignored", embedding=[1, 0])] == ["a"]


def test_s3_object_storage_uses_tenant_scoped_key():
    class FakeS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, **kwargs):
            self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

        def get_object(self, **kwargs):
            from io import BytesIO
            return {"Body": BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    client = FakeS3()
    storage = S3ObjectStorage(client, "financial-agent")
    key = "tenant/tenant-a/documents/hash/v1/content.txt"
    assert storage.put(key, b"facts", "text/plain") == key
    assert storage.get(key) == b"facts"
    assert ("financial-agent", key) in client.objects


def test_document_indexer_requires_ready_document_and_records_metadata():
    document = Document("doc-1", "tenant-a", "Risk note", "cash flow", "hash", "research")
    store = MemoryVectorStore()
    result = DocumentIndexer(HashingEmbedding(8), store).index(document)
    assert result["embedding_dimension"] == 8
    item = store.search(tenant_id="tenant-a", query="cash", limit=1, embedding=[1] * 8)
    assert item[0]["metadata"]["status"] == "ready"
    assert item[0]["metadata"]["sha256"] == "hash"


def test_document_indexer_rejects_non_ready_document():
    document = Document("doc-2", "tenant-a", "Draft", "cash flow", "hash", "research", status="draft")
    try:
        DocumentIndexer(HashingEmbedding(8), MemoryVectorStore()).index(document)
    except ValueError as exc:
        assert "ready" in str(exc)
    else:
        raise AssertionError("non-ready documents must not be indexed")


def test_openai_embedding_requires_transport_and_rejects_empty_response():
    provider = OpenAICompatibleEmbedding("https://embedding.invalid", "key", "model")
    try:
        provider.embed("text")
    except RuntimeError as exc:
        assert "transport" in str(exc)
    else:
        raise AssertionError("missing transport must fail closed")

    empty = OpenAICompatibleEmbedding(
        "https://embedding.invalid", "key", "model", transport=lambda **_: {"data": [{}]}
    )
    try:
        empty.embed("text")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("empty vectors must fail closed")
