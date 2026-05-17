"""Dependencias FastAPI: validacion de JWT, roles y propagacion de correlation_id."""
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
) -> str:
    return x_correlation_id or uuid4().hex


def get_client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticacion requerida.")
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if payload.get("type") == "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token de refresh no es valido para acceso.")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.active.is_(True)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado o inactivo.")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol administrador requerido.")
    return current_user
