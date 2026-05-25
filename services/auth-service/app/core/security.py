"""Hash de contrasenas, validacion de fortaleza, emision y verificacion de JWT.

================================================================================
PROPOSITO
================================================================================
Este modulo es el "muro de seguridad" del sistema. Contiene tres bloques:

  1. Hash de contrasenas (bcrypt): guardamos en BD solo el hash, nunca la
     contrasena en plano. Verificamos comparando hashes (resistente a timing).

  2. Validacion de fortaleza: politica unificada de contrasenas (≥8 chars,
     mayuscula, minuscula, digito, simbolo) aplicada en registro y cambio.

  3. Emision y verificacion de JWT (HS256): emitimos tokens firmados con una
     clave SECRETA COMPARTIDA entre todos los microservicios. Cada servicio
     puede verificar el token LOCALMENTE sin llamar de vuelta al Auth Service.
     Esto es SSO (Single Sign-On) con propagacion stateless.

================================================================================
DECISIONES DE DISENO
================================================================================
- Algoritmo HS256 (HMAC-SHA256): mas simple que RS256 (asimetrico) y suficiente
  para el MVP academico. En produccion real se usaria RS256 para que el secreto
  privado quede solo en Auth y los demas servicios solo tengan el publico.
- audience="tienda-digital-services" + issuer="tienda-digital-auth": evita
  que un token emitido por otro sistema con el mismo secreto sea aceptado.
- jti (JWT ID) unico por token: permite revocar tokens individuales si en el
  futuro implementamos una blacklist.
- Refresh tokens con TTL largo (dias) + hash almacenado en BD (RefreshToken)
  para poder revocarlos al cerrar sesion.

================================================================================
COMPATIBILIDAD CON MONOLITO LEGACY
================================================================================
El monolito original (Fase 1) hasheaba con pbkdf2_sha256. Para que las cuentas
seed creadas en aquella version sigan funcionando tras la migracion a
microservicios, verify_password detecta el prefijo y usa el algoritmo
correcto. Las cuentas nuevas se hashean con bcrypt.
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# --------------------------------------------------------------------------
# Contexto de passlib configurado solo para bcrypt.
# --------------------------------------------------------------------------
# bcrypt es la opcion estandar de la industria: hash adaptativo (work factor
# ajustable), resistente a tablas arcoiris y a aceleracion por GPU.
# IMPORTANTE: requiere bcrypt==4.0.1 + passlib==1.7.4 (versiones pinned en
# requirements.txt). bcrypt 5.x rompe la compatibilidad con passlib 1.7.4.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ═════════════════════════════════════════════════════════════════════════
# HASH DE CONTRASENAS
# ═════════════════════════════════════════════════════════════════════════


def _verify_seed_pbkdf2(plain_password: str, stored_hash: str) -> bool:
    """Verifica un hash pbkdf2_sha256 generado por el seed del monolito legacy.

    Formato esperado: `pbkdf2_sha256$<rounds>$<salt>$<hash_base64>`

    Esta funcion EXISTE solo para que las cuentas migradas del monolito
    (creadas con Django/passlib pbkdf2_sha256) sigan funcionando. Las
    contrasenas nuevas se hashean siempre con bcrypt.
    """
    try:
        # Desempacar las 4 partes del formato: prefijo, rounds, salt, hash.
        _, rounds, salt, expected_hash = stored_hash.split("$", 3)
        # Re-derivar el hash con los mismos parametros y comparar.
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            int(rounds),
            dklen=32,
        )
        calculated = base64.b64encode(digest).decode("utf-8")
        return calculated == expected_hash
    except ValueError:
        # Si el hash no tiene el formato esperado, devolvemos False (no es match)
        # en vez de levantar para que el caller lo trate como contrasena invalida.
        return False


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifica una contrasena en plano contra su hash almacenado.

    Detecta automaticamente el algoritmo (pbkdf2 legacy o bcrypt) y aplica
    el verificador correcto. Devuelve True si coinciden, False en cualquier
    otro caso (incluyendo formatos invalidos).
    """
    if stored_hash.startswith("pbkdf2_sha256$"):
        return _verify_seed_pbkdf2(plain_password, stored_hash)
    return pwd_context.verify(plain_password, stored_hash)


def get_password_hash(password: str) -> str:
    """Genera un hash bcrypt de la contrasena para almacenamiento.

    SIEMPRE bcrypt para cuentas nuevas. passlib aplica un salt aleatorio
    por contrasena para que dos cuentas con la misma contrasena tengan
    hashes distintos en BD.
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> None:
    """Aplica la politica de contrasenas del sistema.

    Levanta ValueError con un mensaje especifico si la contrasena no cumple
    algun criterio. El caller (endpoint /auth/register) captura el ValueError
    y lo traduce a HTTP 422 con el detalle al usuario.

    Politica:
      - Minimo 8 caracteres
      - Al menos una mayuscula
      - Al menos una minuscula
      - Al menos un digito
      - Al menos un caracter especial de la lista permitida
    """
    if len(password) < 8:
        raise ValueError("La contrasena debe tener minimo 8 caracteres.")
    if not any(c.isupper() for c in password):
        raise ValueError("La contrasena debe incluir una mayuscula.")
    if not any(c.islower() for c in password):
        raise ValueError("La contrasena debe incluir una minuscula.")
    if not any(c.isdigit() for c in password):
        raise ValueError("La contrasena debe incluir un numero.")
    if not any(c in "!@#$%^&*()_+-=[]{};:,.<>?/" for c in password):
        raise ValueError("La contrasena debe incluir un caracter especial.")


# ═════════════════════════════════════════════════════════════════════════
# JSON WEB TOKENS (JWT)
# ═════════════════════════════════════════════════════════════════════════


def create_access_token(subject: str, role: str, email: str | None = None) -> str:
    """Emite un JWT de acceso firmado con HS256 + clave compartida.

    El token contiene:
      - sub: identificador del usuario (string del user.id)
      - role: "customer" o "admin" — usado por los services para autorizar
      - email: opcional, util para logs y debug en los demas services
      - exp: timestamp de expiracion (default 60 min, configurable en settings)
      - iss: emisor — los validadores lo verifican para evitar tokens ajenos
      - aud: audiencia — idem
      - jti: id unico del token — para futura blacklist si se necesita

    Lo emiten /auth/login, /auth/register y /auth/refresh. Cada microservicio
    lo valida localmente con decode_token() en su middleware/dependencia.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iss": "tienda-digital-auth",
        "aud": "tienda-digital-services",
        "jti": uuid4().hex,
    }
    if email:
        payload["email"] = email
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    """Emite un refresh token con TTL largo (dias).

    Devuelve (token, expires_at) para que el caller pueda guardar el hash
    en la tabla RefreshToken con su fecha de expiracion. Los refresh tokens
    se almacenan hasheados (sha256) en BD para poder revocarlos al hacer
    logout o al detectar abuso.

    El campo `type: refresh` lo distingue de un access token para que un
    refresh no pueda usarse accidentalmente como access (y viceversa).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expires_at,
        "iss": "tienda-digital-auth",
        "aud": "tienda-digital-services",
        "jti": uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str) -> dict[str, Any]:
    """Valida y decodifica un JWT. Levanta ValueError si es invalido.

    Verifica:
      - La firma con la clave HS256 compartida
      - La expiracion (`exp` futuro)
      - El issuer ("tienda-digital-auth") y audience ("tienda-digital-services")
        para rechazar tokens emitidos por otros sistemas que usen la misma
        clave (ej. otro entorno de Tienda Digital).

    Devuelve el payload del token como dict (con claims `sub`, `role`, etc.).
    Lo usan TODOS los microservicios en sus middlewares de autorizacion para
    no tener que llamar al Auth Service en cada request.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience="tienda-digital-services",
            issuer="tienda-digital-auth",
        )
    except JWTError as exc:
        # Cualquier error (firma invalida, expirado, issuer wrong) se traduce
        # a ValueError generico para que el caller decida el HTTP status.
        raise ValueError(f"Token invalido: {exc}") from exc


def hash_token(token: str) -> str:
    """Hashea un token con SHA-256 para almacenarlo en BD.

    Lo usamos para los refresh tokens: guardamos el hash en la columna
    `token_hash` de RefreshToken para poder revocarlos sin almacenar el
    valor original (defensa en profundidad si la BD se filtra).
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
