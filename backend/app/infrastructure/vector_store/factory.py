"""Vector store factory used by API and worker processes."""

from app.core.config import get_settings
from app.infrastructure.vector_store.memory import MemoryVectorStore
from app.infrastructure.vector_store.qdrant import QdrantVectorStore


def create_vector_store():
    settings = get_settings()
    if settings.vector_store_backend == "qdrant":
        return QdrantVectorStore(
            url=settings.vector_store_url,
            collection=settings.qdrant_collection,
            dimension=settings.embedding_dimension,
            api_key=settings.qdrant_api_key,
            timeout=settings.qdrant_timeout_seconds,
        )
    return MemoryVectorStore()


def check_vector_store() -> bool:
    try:
        store = create_vector_store()
        return bool(getattr(store, "is_ready", lambda: True)())
    except Exception:  # noqa: BLE001 - readiness must not expose dependency details.
        return False
