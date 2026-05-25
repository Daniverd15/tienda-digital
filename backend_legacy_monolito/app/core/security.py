"""Utilidades de seguridad del monolito legacy.

Contiene hash/verificacion de contrasenas, politica de fortaleza y emision/
lectura de JWT. Mantiene compatibilidad con hashes PBKDF2 sembrados en datos
iniciales mientras usa bcrypt para nuevas contrasenas.
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _verify_seed_pbkdf2(plain_password: str, stored_hash: str) -> bool:
    """Verifica hashes PBKDF2 heredados del seed inicial de la base."""
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
    """Valida contrasena contra PBKDF2 legacy o bcrypt actual."""
    if stored_hash.startswith("pbkdf2_sha256$"):
        return _verify_seed_pbkdf2(plain_password, stored_hash)
    return pwd_context.verify(plain_password, stored_hash)


def get_password_hash(password: str) -> str:
    """Genera hash bcrypt para contrasenas nuevas o actualizadas."""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> None:
    """Aplica la politica minima de seguridad de contrasenas del MVP."""
    if len(password) < 8:
        raise ValueError("La contrasena debe tener minimo 8 caracteres.")
    if not any(char.isupper() for char in password):
        raise ValueError("La contrasena debe incluir una mayuscula.")
    if not any(char.islower() for char in password):
        raise ValueError("La contrasena debe incluir una minuscula.")
    if not any(char.isdigit() for char in password):
        raise ValueError("La contrasena debe incluir un numero.")
    if not any(char in "!@#$%^&*()_+-=[]{};:,.<>?/" for char in password):
        raise ValueError("La contrasena debe incluir un caracter especial.")


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un JWT de acceso con subject, rol y expiracion."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decodifica y valida un JWT; lanza ValueError si no es confiable."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Token invalido o expirado.") from exc
