"""Dependencias de autenticacion y autorizacion del monolito legacy.

Centraliza la lectura del bearer token, la decodificacion JWT y las reglas de
rol que protegen endpoints de cliente y administrador. Estas funciones se usan
como Depends(...) en rutas para mantener autorizacion consistente.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resuelve el usuario activo asociado al JWT recibido en la request."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticacion requerida.")
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = db.query(User).filter(User.id == int(payload["sub"]), User.active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado o inactivo.")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Exige rol admin para operaciones de backoffice."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol administrador requerido.")
    return current_user


def require_customer(current_user: User = Depends(get_current_user)) -> User:
    """Permite clientes y admins en rutas de experiencia de compra."""
    if current_user.role not in {"customer", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol cliente requerido.")
    return current_user
