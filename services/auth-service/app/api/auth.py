"""Endpoints de autenticacion: register, login, refresh, logout, me.

================================================================================
PROPOSITO
================================================================================
Implementa los flujos de identidad del sistema (RF-01 del SRS):
  - POST /register: crea cuenta de cliente, valida fortaleza, envia bienvenida
  - POST /login:    valida credenciales y emite par de tokens
  - POST /refresh:  rota el refresh token (revoca el viejo + emite nuevo par)
  - POST /logout:   revoca todos los refresh tokens del usuario
  - GET  /me:       devuelve el perfil del usuario autenticado

================================================================================
MODELO DE TOKENS
================================================================================
Cada login (o register) emite DOS tokens:
  - access_token (vida corta, 60min): se envia en Authorization: Bearer <jwt>
    en cada request. Es validado localmente por los demas microservicios
    sin necesidad de llamar al Auth Service (SSO con JWT compartido).
  - refresh_token (vida larga, 7 dias): se almacena hasheado en BD. Se usa
    para obtener un nuevo access_token sin pedir credenciales otra vez.
    Cuando se usa, se ROTA (revoca + emite nuevo) para mitigar token theft.

================================================================================
BITACORA DE ACCESOS
================================================================================
Cada accion (register, login, login_failed, refresh, logout) deja una entrada
en la tabla AccessLog con: user_id, action, IP, user_agent, correlation_id.
Lo usa el admin para detectar abuso (multiples login_failed desde misma IP)
y para auditoria (RNF-03 trazabilidad).
"""
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


# ═════════════════════════════════════════════════════════════════════════
# HELPERS PRIVADOS
# ═════════════════════════════════════════════════════════════════════════


def _log_access(
    db: Session,
    user_id: int | None,
    action: str,
    ip: str | None,
    ua: str | None,
    correlation_id: str | None,
) -> None:
    """Registra una entrada en la bitacora de accesos (AccessLog).

    user_id puede ser None cuando registramos un login_failed sin email
    valido (ej. el cliente escribio un correo que no existe). En ese caso
    la bitacora queda como "intento de acceso anonimo" para que el admin
    pueda detectar ataques de credential stuffing.

    NO hace commit: el caller debe commitear en su transaccion (asi si el
    flujo falla a mitad, todo se hace rollback junto).
    """
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
    """Emite un par access_token + refresh_token para `user`.

    El refresh_token se almacena hasheado (SHA-256) en RefreshToken para
    poder revocarlo despues sin guardar el valor original. El access_token
    NO se almacena (es stateless y vive solo en el cliente).

    Devuelve TokenResponse listo para serializar como JSON al frontend.
    """
    # Access token: incluye sub (user_id), role y email para que los demas
    # services puedan autorizar sin call-back.
    access = create_access_token(subject=str(user.id), role=user.role, email=user.email)
    # Refresh token: incluye sub + type="refresh" + jti unico.
    refresh, refresh_exp = create_refresh_token(subject=str(user.id))
    # Almacenamos el HASH (no el token mismo) por defensa en profundidad.
    # Si la BD se filtra, el atacante no puede usar los refresh directamente.
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


# ═════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    """Crea una cuenta nueva de cliente y devuelve el par de tokens.

    Flujo:
    1. Validar que el email no exista (409 Conflict si ya esta registrado).
    2. Validar fortaleza de la contrasena (422 si no cumple politica).
    3. Crear el User con password hasheado bcrypt y role="customer".
    4. Loguear el evento "register" en AccessLog (con IP y UA).
    5. Emitir par de tokens.
    6. Enviar correo de bienvenida via SMTP (best-effort, no bloqueante).
    7. Commit y devolver tokens (201 Created).
    """
    # ─── 1. Verificar email unico (case-insensitive) ────────────────────
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(409, "El correo ya esta registrado.")

    # ─── 2. Validar fortaleza de contrasena ─────────────────────────────
    # validate_password_strength lanza ValueError con mensaje especifico
    # ("debe incluir mayuscula", "debe incluir digito", etc.).
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        # 422 Unprocessable Entity: el dato es semanticamente invalido.
        raise HTTPException(422, str(exc)) from exc

    # ─── 3. Crear el User ────────────────────────────────────────────────
    # email normalizado a lowercase para evitar duplicados case-sensitive.
    # password siempre hasheado con bcrypt (nunca en plano en BD).
    # role="customer" por defecto: no se permite auto-registrar admins.
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        password_hash=get_password_hash(payload.password),
        role="customer",
        active=True,
    )
    db.add(user)
    # flush para obtener user.id sin commit (lo necesitamos para AccessLog).
    db.flush()

    # ─── 4. Bitacora del registro ────────────────────────────────────────
    ip, ua = get_client_meta(request)
    _log_access(db, user.id, "register", ip, ua, correlation_id)

    # ─── 5. Emitir par de tokens y persistir refresh hash ────────────────
    tokens = _issue_tokens(db, user)

    # Commit atomico: User + AccessLog + RefreshToken se persisten juntos.
    db.commit()
    db.refresh(user)

    # ─── 6. Correo de bienvenida (best-effort) ───────────────────────────
    # send_welcome_email es no bloqueante: si SMTP cae, solo loguea WARN y
    # la cuenta queda creada igual.
    send_welcome_email(user.name, user.email)

    return tokens


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    """Autentica al usuario y devuelve par de tokens si las credenciales son correctas.

    IMPORTANTE: el endpoint /api/auth/login tiene rate-limit en el gateway
    (5 req/min por IP) para mitigar brute force. Despues de 5 intentos
    fallidos en un minuto, el gateway responde 429 sin tocar este endpoint.

    Devuelve 401 Unauthorized si:
      - El email no existe
      - El usuario esta inactivo (User.active = False)
      - La contrasena no coincide

    Cualquier fallo se registra como "login_failed" en AccessLog. El admin
    puede consultar la bitacora para detectar patrones de abuso.
    """
    # Buscar usuario por email (case-insensitive) Y que este activo.
    user = db.query(User).filter(User.email == payload.email.lower(), User.active.is_(True)).first()
    ip, ua = get_client_meta(request)

    # Si no existe O la contrasena es incorrecta → 401.
    # Usamos el mismo mensaje para AMBOS casos para no revelar al atacante
    # si un email esta registrado o no (defensa contra enumeracion de cuentas).
    if not user or not verify_password(payload.password, user.password_hash):
        # Loguear el fallo. user.id es None si el email no existe.
        _log_access(db, user.id if user else None, "login_failed", ip, ua, correlation_id)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales invalidas.")

    # Credenciales correctas: loguear exito y emitir tokens.
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
    """Rota un refresh_token: revoca el viejo y emite uno nuevo + nuevo access.

    Es el unico endpoint que acepta un refresh_token (los demas usan el
    access_token). Se llama desde el frontend cuando el access expira
    (401) para evitar pedir credenciales al usuario.

    Flujo:
    1. Decodificar el JWT (valida firma, expiracion, iss/aud).
    2. Verificar que sea tipo="refresh" (no aceptamos access tokens).
    3. Buscar el hash del token en RefreshToken; verificar no revocado y no expirado.
    4. Verificar que el usuario asociado siga activo.
    5. ROTAR: marcar el viejo como revoked=True + emitir un nuevo par.

    La rotacion mitiga token theft: si un atacante roba el refresh_token,
    al usarlo solo puede emitirlo UNA vez. El usuario legitimo (cuando vea
    su sesion cerrada) notara que algo paso y podra cambiar contrasena.
    """
    # ─── 1. Decodificar JWT (firma, expiracion, iss/aud) ─────────────────
    try:
        claims = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    # ─── 2. Verificar que sea un refresh, no un access ───────────────────
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token no es de refresh.")

    # ─── 3. Buscar en BD el hash del token (no el token completo) ────────
    # Si fue revocado por logout o por otro refresh anterior, no esta valido.
    token_hash = hash_token(payload.refresh_token)
    stored = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked.is_(False))
        .first()
    )
    # Verificamos tambien expires_at por si el DB tiene un valor desactualizado
    # (paranoia: idealmente decode_token ya validaria exp, pero doble check).
    if not stored or stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalido o expirado.")

    # ─── 4. Verificar que el usuario siga activo ────────────────────────
    user = db.query(User).filter(User.id == stored.user_id, User.active.is_(True)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo.")

    # ─── 5. ROTACION: revocar el viejo + emitir uno nuevo ───────────────
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
    """Cierra sesion del usuario revocando TODOS sus refresh tokens activos.

    Estrategia "kill switch global": no solo revoca el refresh del navegador
    actual, sino TODOS los del usuario en cualquier dispositivo. Esto es
    util si el usuario sospecha que su cuenta esta comprometida.

    El access_token actual del cliente sigue siendo valido hasta su
    expiracion natural (max 60min). Esto es una limitacion conocida de JWT
    stateless: no podemos invalidar el access en tiempo real sin agregar
    una blacklist en Redis (no implementado en MVP).
    """
    # Revocar TODOS los refresh tokens activos del usuario en una sola query.
    # No iteramos: hacemos un UPDATE masivo por eficiencia.
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
    """Devuelve el perfil del usuario autenticado.

    El frontend lo llama al cargar la SPA para saber si el token guardado
    sigue valido y obtener los datos del usuario (nombre, role, email).
    Si el token es invalido, get_current_user levanta 401 automaticamente.
    """
    return current_user
