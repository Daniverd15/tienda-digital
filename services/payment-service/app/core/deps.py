"""JWT local + correlation id."""
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> str:
    return x_correlation_id or uuid4().hex


def _decode(token: str) -> dict:
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
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticacion requerida.")
    claims = _decode(credentials.credentials)
    if claims.get("type") == "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de refresh no es valido.")
    return claims


def require_admin(claims: dict = Depends(get_current_user_claims)) -> dict:
    if claims.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol administrador requerido.")
    return claims
