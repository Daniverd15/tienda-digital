from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, validate_password_strength, verify_password
from app.models import User
from app.schemas import ApiMessage, TokenResponse, UserCreate, UserLogin, UserPublic, UserUpdate
from app.services.audit_service import add_audit_log


router = APIRouter(tags=["Autenticacion"])


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="El correo ya esta registrado.")
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        password_hash=get_password_hash(payload.password),
        role="customer",
        active=True,
    )
    db.add(user)
    db.flush()
    add_audit_log(db, user_id=user.id, action="register", entity="users", entity_id=user.id)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower(), User.active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas.")
    add_audit_log(db, user_id=user.id, action="login", entity="users", entity_id=user.id)
    db.commit()
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/auth/logout", response_model=ApiMessage)
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    add_audit_log(db, user_id=current_user.id, action="logout", entity="users", entity_id=current_user.id)
    db.commit()
    return ApiMessage(message="Sesion cerrada en el cliente.")


@router.get("/auth/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/admin/profile", response_model=UserPublic)
def update_admin_profile(
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    previous = {"name": current_user.name, "phone": current_user.phone, "active": current_user.active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    add_audit_log(
        db,
        user_id=current_user.id,
        action="update_admin_profile",
        entity="users",
        entity_id=current_user.id,
        previous_value=previous,
        new_value=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(current_user)
    return current_user

