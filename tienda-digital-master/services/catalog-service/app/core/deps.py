"""Dependencias FastAPI: validacion local de JWT (SSO compartido).

Importante: Catalog NO consulta auth_db. Confia en la firma del JWT (HS256
con la misma clave que Auth emitio). Solo necesita verificar la firma y
extraer sub + role del payload. Esto evita acoplamiento y latencia extra.
"""
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> str:
    """Propaga correlation id para cache, auditoria y llamadas cruzadas."""
    return x_correlation_id or uuid4().hex


def _decode(token: str) -> dict:
    """Valida firma, issuer y audience del JWT compartido."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience="tienda-digital-services",
            issuer="tienda-digital-auth",
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token invalido: {exc}") from exc


def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Devuelve los claims del JWT (sub, role, email). NO consulta BD."""
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticacion requerida.")
    claims = _decode(credentials.credentials)
    if claims.get("type") == "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de refresh no es valido para acceso.")
    return claims


def require_admin(claims: dict = Depends(get_current_user_claims)) -> dict:
    """Exige rol admin para mutaciones de catalogo."""
    if claims.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol administrador requerido.")
    return claims
