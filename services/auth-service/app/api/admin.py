"""Endpoints administrativos:
- /admin/me  : perfil y actualizacion del admin (incluye cambio de contrasena)
- /admin/customers/* : listado de clientes para que Commerce los consulte
- /admin/access-logs : bitacora de accesos
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.security import get_password_hash, validate_password_strength
from app.models import AccessLog, User
from app.schemas import (
    AccessLogPublic,
    AdminProfileUpdate,
    CustomerPublic,
    UserPublic,
)


router = APIRouter(prefix="/admin", tags=["Administracion"])


@router.get("/me", response_model=UserPublic)
def admin_me(current_admin: User = Depends(require_admin)):
    return current_admin


@router.put("/me", response_model=UserPublic)
def update_admin_me(
    payload: AdminProfileUpdate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    new_password = data.pop("new_password", None)
    for field, value in data.items():
        setattr(current_admin, field, value)
    if new_password:
        try:
            validate_password_strength(new_password)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        current_admin.password_hash = get_password_hash(new_password)
    db.commit()
    db.refresh(current_admin)
    return current_admin


@router.get("/customers", response_model=list[CustomerPublic])
def list_customers(
    search: str | None = Query(default=None, max_length=120),
    only_active: bool = Query(default=True),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.role == "customer")
    if only_active:
        query = query.filter(User.active.is_(True))
    if search:
        like = f"%{search.lower()}%"
        query = query.filter((User.email.ilike(like)) | (User.name.ilike(like)))
    return query.order_by(User.created_at.desc()).limit(500).all()


@router.get("/customers/{customer_id}", response_model=CustomerPublic)
def get_customer(
    customer_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == customer_id, User.role == "customer").first()
    if not user:
        raise HTTPException(404, "Cliente no encontrado.")
    return user


@router.get("/access-logs", response_model=list[AccessLogPublic])
def access_logs(
    limit: int = Query(default=200, le=1000),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(AccessLog).order_by(AccessLog.id.desc()).limit(limit).all()
