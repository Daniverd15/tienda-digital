"""Endpoints de autenticacion: register, login, refresh, logout, me."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import (
    get_client_meta,
    get_correlation_id,
    get_current_user,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    validate_password_strength,
    verify_password,
)
from app.core.config import settings
from app.models import AccessLog, RefreshToken, User
from app.schemas import (
    ApiMessage,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserPublic,
)
from app.services.mailer import send_welcome_email


router = APIRouter(tags=["Autenticacion"])


def _log_access(
    db: Session,
    user_id: int | None,
    action: str,
    ip: str | None,
    ua: str | None,
    correlation_id: str | None,
) -> None:
    db.add(
        AccessLog(
            user_id=user_id,
            action=action,
            ip=ip,
            user_agent=ua,
            correlation_id=correlation_id,
        )
    )


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access = create_access_token(subject=str(user.id), role=user.role, email=user.email)
    refresh, refresh_exp = create_refresh_token(subject=str(user.id))
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=refresh_exp,
        )
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in_minutes=settings.jwt_access_ttl_minutes,
        user=UserPublic.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(409, "El correo ya esta registrado.")
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

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
    ip, ua = get_client_meta(request)
    _log_access(db, user.id, "register", ip, ua, correlation_id)
    tokens = _issue_tokens(db, user)
    db.commit()
    db.refresh(user)

    # Correo de bienvenida (no bloqueante)
    send_welcome_email(user.name, user.email)

    return tokens


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    user = db.query(User).filter(User.email == payload.email.lower(), User.active.is_(True)).first()
    ip, ua = get_client_meta(request)
    if not user or not verify_password(payload.password, user.password_hash):
        _log_access(db, user.id if user else None, "login_failed", ip, ua, correlation_id)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales invalidas.")
    _log_access(db, user.id, "login", ip, ua, correlation_id)
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    try:
        claims = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token no es de refresh.")

    token_hash = hash_token(payload.refresh_token)
    stored = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
        .first()
    )
    if not stored or stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalido o expirado.")

    user = db.query(User).filter(User.id == stored.user_id, User.active.is_(True)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo.")

    # Rotacion: revocamos el refresh usado y emitimos uno nuevo
    stored.revoked = True
    ip, ua = get_client_meta(request)
    _log_access(db, user.id, "refresh", ip, ua, correlation_id)
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout", response_model=ApiMessage)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    # Revocamos TODOS los refresh tokens del usuario (corte de sesion)
    (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == current_user.id, RefreshToken.revoked.is_(False))
        .update({RefreshToken.revoked: True})
    )
    ip, ua = get_client_meta(request)
    _log_access(db, current_user.id, "logout", ip, ua, correlation_id)
    db.commit()
    return ApiMessage(message="Sesion cerrada.")


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
