"""FastAPI 依赖：共享容器、认证主体和租户上下文。"""

from fastapi import Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.container import Container
from app.core.auth import Principal, authenticate, require_permission


# PoC 使用进程内单例；生产环境应替换为数据库、缓存和审计实现。
container = Container()
bearer = HTTPBearer(auto_error=False)


def get_container() -> Container:
    return container


def current_principal(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> Principal:
    return authenticate(f"Bearer {credentials.credentials}" if credentials else None)


def require_api_permission(permission: str):
    def dependency(principal: Principal = Security(current_principal)) -> Principal:
        from app.core.config import get_settings
        settings = get_settings()
        if settings.app_env != "production" and settings.auth_dev_mode:
            return principal
        require_permission(principal, permission)
        return principal
    return dependency


def request_context(
    principal: Principal = Security(current_principal),
    x_dev_tenant_id: str | None = Header(default=None, alias="X-Dev-Tenant-Id"),
    x_dev_user_id: str | None = Header(default=None, alias="X-Dev-User-Id"),
) -> tuple[str, str]:
    # 开发主体只接受固定演示租户，避免请求头伪造任意租户访问。
    from app.core.config import get_settings
    settings = get_settings()
    if settings.app_env != "production" and settings.auth_dev_mode:
        return x_dev_tenant_id or principal.tenant_id, x_dev_user_id or principal.subject
    return principal.tenant_id, principal.subject
