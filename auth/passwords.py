"""Hash de senha com Argon2id.

# Portado de backend/app/core/security.py@e027e41 (verify_password, get_password_hash),
# trocando passlib por argon2-cffi (ADM-004).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
MIN_PASSWORD_LENGTH = 10


class WeakPasswordError(ValueError):
    pass


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"a senha precisa de ao menos {MIN_PASSWORD_LENGTH} caracteres")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Hash fixo usado para gastar o mesmo tempo quando o usuário não existe.
DUMMY_HASH = _hasher.hash("lipidence-modular-dummy-password")
