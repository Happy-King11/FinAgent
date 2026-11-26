"""Backend-selected infrastructure wiring."""

from app.core.config import get_settings
from app.infrastructure.cache.redis import RedisCache
from app.infrastructure.cache.client import create_redis_client
from app.repositories.memory import ConsultationRepository, DocumentRepository, ProductRepository


def build_repositories():
    settings = get_settings()
    if settings.persistence_backend == "memory":
        if settings.app_env == "production":
            raise RuntimeError("production cannot use memory repositories")
        return {
            "products": ProductRepository(),
            "documents": DocumentRepository(),
            "consultations": ConsultationRepository(),
        }
    if settings.persistence_backend != "postgresql":
        raise RuntimeError(f"unsupported persistence backend: {settings.persistence_backend}")
    raise RuntimeError("postgresql repository wiring is not enabled until migrations are applied")


def build_cache():
    settings = get_settings()
    if settings.app_env == "production" or settings.persistence_backend == "postgresql":
        return RedisCache(create_redis_client())
    return None


def check_redis() -> bool:
    try:
        create_redis_client().ping()
        return True
    except Exception:  # noqa: BLE001 - readiness should report dependency failure.
        return False
