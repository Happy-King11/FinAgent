"""FastAPI 应用入口、健康检查和统一异常转换。"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import container
from app.api.v1.router import router, seed_demo
from app.core.exceptions import DomainError
from app.core.config import get_settings
from app.core.dependencies import check_redis
from app.infrastructure.database import check_database
from app.infrastructure.object_storage.factory import check_object_storage
from app.infrastructure.vector_store.factory import check_vector_store
from app.llm.embeddings import OpenAICompatibleEmbedding
from app.llm.openai_compatible import OpenAICompatibleClient


app = FastAPI(title="Financial Consultation Agent", version="0.1.0")
settings = get_settings()
if settings.cors_origins:
    # 生产只允许配置的前端来源，禁止通配符携带凭证。
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
# API 路由统一挂在版本前缀下，健康检查保持无版本路径。
app.include_router(router, prefix="/api/v1")


def _check_embedding_provider() -> bool:
    """Probe the configured OpenAI-compatible embedding contract safely."""
    try:
        provider = OpenAICompatibleEmbedding(
            settings.embedding_base_url,
            settings.embedding_api_key,
            settings.embedding_model,
            settings.embedding_dimension,
            settings.embedding_timeout_seconds,
        )
        vector = provider.embed("health")
        return len(vector) == settings.embedding_dimension
    except Exception:  # noqa: BLE001
        return False


def _check_llm_provider() -> bool:
    """Check configured LLM endpoint without sending a user prompt."""
    if settings.llm_provider != "openai_compatible" or not settings.llm_base_url:
        return False
    return OpenAICompatibleClient(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
    ).is_ready(timeout_seconds=settings.provider_connect_timeout_seconds)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> JSONResponse:
    settings = get_settings()
    if settings.persistence_backend == "memory" and settings.app_env != "production":
        return JSONResponse({"status": "ready", "dependencies": {"repository": "memory", "retrieval": settings.vector_store_backend, "audit": "ready"}})
    checks = {"database": check_database(), "redis": check_redis(), "vector_store": check_vector_store()}
    if settings.embedding_provider == "openai_compatible":
        checks["embedding"] = _check_embedding_provider()
    if settings.llm_provider == "openai_compatible":
        checks["llm"] = _check_llm_provider()
    if settings.object_storage_enabled:
        checks["object_storage"] = check_object_storage()
    ready_state = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ready_state else "not_ready", "dependencies": checks},
        status_code=status.HTTP_200_OK if ready_state else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    # 对外只返回稳定错误码和消息，不泄露堆栈或内部连接信息。
    return JSONResponse(status_code=exc.status_code, content={"request_id": "", "trace_id": "", "data": None, "error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "INVALID_ARGUMENT", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"request_id": "", "trace_id": "", "data": None, "error": {"code": detail.get("code", "INVALID_ARGUMENT"), "message": detail.get("message", "request failed")}})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"request_id": "", "trace_id": "", "data": None, "error": {"code": "INVALID_ARGUMENT", "message": "request validation failed"}})


seed_demo(container)
