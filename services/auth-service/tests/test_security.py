"""Tests unitarios de security.py (no requieren MySQL)."""
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_token,
    validate_password_strength,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    """El hash bcrypt valida la clave correcta y rechaza una incorrecta."""
    h = get_password_hash("Pa$$w0rd!")
    assert verify_password("Pa$$w0rd!", h) is True
    assert verify_password("incorrecta", h) is False


def test_password_strength_rules():
    """La politica de contrasena cubre longitud, casos, numero y simbolo."""
    validate_password_strength("Abcdef1!")
    with pytest.raises(ValueError):
        validate_password_strength("corta")
    with pytest.raises(ValueError):
        validate_password_strength("sinmayuscula1!")
    with pytest.raises(ValueError):
        validate_password_strength("SINMINUSCULA1!")
    with pytest.raises(ValueError):
        validate_password_strength("SinNumero!")
    with pytest.raises(ValueError):
        validate_password_strength("SinEspecial1")


def test_access_token_roundtrip():
    """El access token conserva claims usados por los microservicios."""
    token = create_access_token(subject="42", role="customer", email="x@y.com")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "customer"
    assert payload["email"] == "x@y.com"


def test_refresh_token_marked_as_refresh():
    """Los refresh tokens llevan type=refresh para rechazarlos como access."""
    token, _ = create_refresh_token(subject="7")
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == "7"


def test_hash_token_is_sha256_hex():
    """El hash de refresh token se guarda como SHA-256 hexadecimal."""
    assert len(hash_token("abc")) == 64
