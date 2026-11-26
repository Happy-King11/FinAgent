"""Document indexing service combining embeddings and a rebuildable vector store."""

from datetime import datetime, timezone
from typing import Any

from app.infrastructure.vector_store.base import VectorStore
from app.llm.embeddings import EmbeddingProvider


class DocumentIndexer:
    def __init__(self, embedding_provider: EmbeddingProvider, vector_store: VectorStore) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def index(self, document: Any) -> dict[str, Any]:
        if document.status != "ready":
            raise ValueError("only ready documents can be indexed")
        embedding = self.embedding_provider.embed(document.content)
        if not embedding:
            raise ValueError("embedding provider returned an empty vector")
        expected_dimension = getattr(self.embedding_provider, "dimension", 0)
        if expected_dimension and len(embedding) != expected_dimension:
            raise ValueError("embedding dimension does not match provider configuration")
        expires_at = getattr(document, "authorization_expires_at", None)
        authorization_expired = bool(
            expires_at and expires_at <= datetime.now(timezone.utc)
        )
        self.vector_store.upsert(
            document_id=document.id,
            tenant_id=document.tenant_id,
            text=document.content,
            embedding=embedding,
            metadata={
                "title": document.title,
                "source": document.source,
                "status": document.status,
                "object_version": document.object_version,
                "sha256": document.sha256,
                "authorization_expired": authorization_expired,
            },
        )
        return {
            "document_id": document.id,
            "embedding_dimension": len(embedding),
            "index_status": "indexed",
        }
