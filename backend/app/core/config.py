"""环境配置基线；生产环境应由 Secret Manager 注入敏感配置。"""

import os
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

try:
    from dotenv import load_dotenv
    _PROJECT_ROOT = Path(__file__).resolve().parents[2]
    # Explicit process variables win.  For host-side development, .env.local
    # overrides the shared/cloud defaults in .env without being copied into
    # Docker images or committed to source control.
    load_dotenv(_PROJECT_ROOT / ".env.local")
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    # 依赖尚未安装时仍允许外部环境变量驱动配置。
    pass


class Settings(BaseModel):
    app_env: str = "development"
    app_name: str = "financial-agent"
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    default_tenant_id: str = "tenant-demo"
    default_user_id: str = "user-demo"
    audit_genesis_prefix: str = "financial-agent:audit:genesis"
    llm_provider: str = "openai_compatible"
    llm_model: str = "deepseek-v4-pro"
    llm_timeout_seconds: int = Field(default=60, ge=1)
    llm_max_tokens: int = Field(default=1200, ge=1, le=8192)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    default_request_timeout_seconds: int = Field(default=60, ge=1)
    database_url: str = "sqlite:///./financial_agent.db"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "financial-agent"
    object_storage_enabled: bool = False
    redis_idempotency_enabled: bool = False
    vector_store_backend: str = "memory"
    vector_store_url: str = "http://localhost:8000"
    qdrant_api_key: str = ""
    qdrant_collection: str = "financial-agent-documents"
    qdrant_timeout_seconds: int = Field(default=10, ge=1)
    embedding_provider: str = "hashing"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "local-hash-v1"
    embedding_model_revision: str = ""
    embedding_dimension: int = Field(default=64, ge=1)
    embedding_timeout_seconds: int = Field(default=60, ge=1)
    embedding_batch_size: int = Field(default=16, ge=1, le=512)
    provider_connect_timeout_seconds: int = Field(default=10, ge=1)
    provider_read_timeout_seconds: int = Field(default=60, ge=1)
    vllm_health_url: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    jwt_issuer: str = ""
    jwt_audience: str = "financial-agent"
    jwt_jwks_url: str = ""
    jwt_hs256_secret: str = ""
    # 开发默认只生成固定演示主体；生产校验器会强制关闭该能力。
    auth_dev_mode: bool = True
    allow_memory_fallback: bool = False
    persistence_backend: str = "memory"
    require_auth: bool = True
    cors_origins: list[str] = Field(default_factory=list)
    audit_retention_days: int = Field(default=2555, ge=1)
    worker_broker_url: str = "redis://localhost:6379/1"
    worker_result_backend: str = "redis://localhost:6379/2"

    @model_validator(mode="after")
    def validate_production_safety(self):
        if self.embedding_provider not in {"hashing", "openai_compatible"}:
            raise ValueError("unsupported embedding provider")
        if self.llm_provider not in {"openai_compatible"}:
            raise ValueError("unsupported LLM provider")
        if self.vector_store_backend not in {"memory", "qdrant"}:
            raise ValueError("unsupported vector store backend")
        if self.embedding_provider == "openai_compatible" and not self.embedding_base_url:
            raise ValueError("openai-compatible embedding requires EMBEDDING_BASE_URL")
        if self.vector_store_backend == "qdrant":
            if not self.vector_store_url:
                raise ValueError("qdrant vector store requires VECTOR_STORE_URL")
            if self.app_env in {"staging", "production"} and not self.vector_store_url.startswith("https://"):
                if self.app_env == "production":
                    raise ValueError("production requires JWT and persistent storage configuration")
                raise ValueError("cloud qdrant requires an HTTPS VECTOR_STORE_URL")
            if self.app_env in {"staging", "production"} and not self.qdrant_api_key:
                raise ValueError("cloud qdrant requires QDRANT_API_KEY")
        if self.app_env == "production" and (
            self.auth_dev_mode
            or self.allow_memory_fallback
            or self.persistence_backend == "memory"
            or self.vector_store_backend == "memory"
            or (not self.jwt_hs256_secret and not self.jwt_jwks_url)
        ):
            raise ValueError("production requires JWT and persistent storage configuration")
        return self


@lru_cache
def get_settings() -> Settings:
    # 缓存配置对象，保证同一进程内依赖读取到一致设置。
    values = {"app_env": os.getenv("APP_ENV", "development")}
    aliases = {
        "api_host": "API_HOST", "api_port": "API_PORT",
        "database_url": "DATABASE_URL", "redis_url": "REDIS_URL", "object_storage_endpoint": "OBJECT_STORAGE_ENDPOINT",
        "object_storage_bucket": "OBJECT_STORAGE_BUCKET", "object_storage_enabled": "OBJECT_STORAGE_ENABLED", "redis_idempotency_enabled": "REDIS_IDEMPOTENCY_ENABLED", "vector_store_backend": "VECTOR_STORE_BACKEND",
        "vector_store_url": "VECTOR_STORE_URL", "qdrant_api_key": "QDRANT_API_KEY", "qdrant_collection": "QDRANT_COLLECTION", "qdrant_timeout_seconds": "QDRANT_TIMEOUT_SECONDS", "embedding_provider": "EMBEDDING_PROVIDER", "embedding_base_url": "EMBEDDING_BASE_URL", "embedding_api_key": "EMBEDDING_API_KEY", "embedding_model": "EMBEDDING_MODEL", "embedding_model_revision": "EMBEDDING_MODEL_REVISION", "embedding_dimension": "EMBEDDING_DIMENSION", "embedding_timeout_seconds": "EMBEDDING_TIMEOUT_SECONDS", "embedding_batch_size": "EMBEDDING_BATCH_SIZE", "vllm_health_url": "VLLM_HEALTH_URL", "llm_provider": "LLM_PROVIDER", "llm_model": "LLM_MODEL", "llm_timeout_seconds": "LLM_TIMEOUT_SECONDS", "llm_max_tokens": "LLM_MAX_TOKENS", "llm_max_retries": "LLM_MAX_RETRIES", "provider_connect_timeout_seconds": "PROVIDER_CONNECT_TIMEOUT_SECONDS", "provider_read_timeout_seconds": "PROVIDER_READ_TIMEOUT_SECONDS",
        "llm_api_key": "LLM_API_KEY", "llm_base_url": "LLM_BASE_URL", "aws_access_key_id": "AWS_ACCESS_KEY_ID", "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY", "jwt_issuer": "JWT_ISSUER",
        "jwt_audience": "JWT_AUDIENCE", "jwt_jwks_url": "JWT_JWKS_URL", "jwt_hs256_secret": "JWT_HS256_SECRET",
        "worker_broker_url": "CELERY_BROKER_URL", "worker_result_backend": "CELERY_RESULT_BACKEND",
        "persistence_backend": "PERSISTENCE_BACKEND", "audit_retention_days": "AUDIT_RETENTION_DAYS",
    }
    for field, env_name in aliases.items():
        if os.getenv(env_name) is not None:
            values[field] = os.environ[env_name]
    for field in ("auth_dev_mode", "allow_memory_fallback", "require_auth", "object_storage_enabled", "redis_idempotency_enabled"):
        env_name = field.upper()
        if os.getenv(env_name) is not None:
            values[field] = os.environ[env_name].lower() in {"1", "true", "yes", "on"}
    return Settings(**values)
