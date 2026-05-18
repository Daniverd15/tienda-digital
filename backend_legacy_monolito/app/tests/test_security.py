from datetime import timedelta

import pytest

from app.core.security import create_access_token, decode_token, validate_password_strength, verify_password


def test_seed_hash_verifies_customer_password():
    stored_hash = "pbkdf2_sha256$260000$customer-seed-salt$BIKHOgXd+/IjEsI1CklyQ8Xm7XyaTCb1TW6ianCDF8U="
    assert verify_password("Cliente123*", stored_hash)
    assert not verify_password("incorrecta", stored_hash)


def test_password_strength_rejects_weak_password():
    with pytest.raises(ValueError):
        validate_password_strength("123")


def test_jwt_roundtrip_contains_subject_and_role():
    token = create_access_token("7", "admin", timedelta(minutes=5))
    payload = decode_token(token)
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"

