"""Hash de contrasenas, validacion de fortaleza, emision y verificacion de JWT.

JWT firmado con clave compartida (HS256) para que cada microservicio pueda validar
el token localmente sin necesidad de llamar al Auth Service en cada peticion (SSO).
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Hash de contrasenas
# ---------------------------------------------------------------------------


def _verify_seed_pbkdf2(plain_password: str, stored_hash: str) -> bool:
    """Compatibilidad con hashes pbkdf2_sha256 generados por el seed del monolito."""
    try:
        _, rounds, salt, expected_hash = stored_hash.split("$", 3)
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
        return False


def verify_password(plain_password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        return _verify_seed_pbkdf2(plain_password, stored_hash)
    return pwd_context.verify(plain_password, stored_hash)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> None:
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


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_access_token(subject: str, role: str, email: str | None = None) -> str:
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
    """Devuelve (token, expires_at) para almacenarlo y rotarlo."""
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
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience="tienda-digital-services",
            issuer="tienda-digital-auth",
        )
    except JWTError as exc:
        raise ValueError(f"Token invalido: {exc}") from exc


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
