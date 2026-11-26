"""JWT/OIDC 认证和最小 RBAC/租户授权校验。"""

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.core.config import get_settings


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: frozenset[str]
    scopes: frozenset[str]
    data_entitlements: frozenset[str]
    organization_id: str | None
    claims: dict[str, Any]

    def can(self, permission: str) -> bool:
        return "admin" in self.roles or permission in self.scopes or permission.split(":")[0] in self.roles

    def can_access_data(self, entitlement: str) -> bool:
        return "*" in self.data_entitlements or entitlement in self.data_entitlements


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        import jwt
        options = {"verify_signature": True, "verify_exp": True, "verify_aud": bool(settings.jwt_audience), "verify_iss": bool(settings.jwt_issuer)}
        kwargs: dict[str, Any] = {"algorithms": ["HS256"], "options": options}
        if settings.jwt_hs256_secret:
            return jwt.decode(token, settings.jwt_hs256_secret, audience=settings.jwt_audience or None, issuer=settings.jwt_issuer or None, **kwargs)
        if settings.jwt_jwks_url:
            client = jwt.PyJWKClient(settings.jwt_jwks_url)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, audience=settings.jwt_audience or None, issuer=settings.jwt_issuer or None, algorithms=["RS256", "ES256"], options=options)
    except ImportError as exc:
        raise HTTPException(503, detail={"code": "AUTH_UNAVAILABLE", "message": "JWT dependency is not installed"}) from exc
    raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "OIDC/JWT verification is not configured"})


def authenticate(authorization: str | None) -> Principal:
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        if settings.app_env != "production" and settings.auth_dev_mode:
            return Principal("dev-user", settings.default_tenant_id, frozenset({"user", "admin"}), frozenset({"*"}), frozenset({"*"}), "local", {"dev": True})
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "Bearer token is required"})
    claims = _decode_token(authorization.split(" ", 1)[1].strip())
    subject = str(claims.get("sub", ""))
    tenant_id = str(claims.get("tenant_id") or claims.get("tenant") or "")
    if not subject or not tenant_id:
        raise HTTPException(403, detail={"code": "TENANT_SCOPE_VIOLATION", "message": "token lacks subject or tenant"})
    roles = frozenset(claims.get("roles", []))
    scopes = frozenset(str(claims.get("scope", "")).split())
    entitlements = frozenset(str(claims.get("data_entitlements", "")).split())
    if not entitlements and isinstance(claims.get("data_entitlements"), list):
        entitlements = frozenset(str(value) for value in claims["data_entitlements"])
    return Principal(subject, tenant_id, roles, scopes, entitlements, str(claims.get("organization_id")) if claims.get("organization_id") else None, claims)


def require_permission(principal: Principal, permission: str) -> None:
    if "*" not in principal.scopes and not principal.can(permission):
        raise HTTPException(403, detail={"code": "PERMISSION_DENIED", "message": "permission denied"})
