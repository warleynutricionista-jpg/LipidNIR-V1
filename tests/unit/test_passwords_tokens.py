import pytest

from lipidence_modular.auth.passwords import WeakPasswordError, hash_password, verify_password
from lipidence_modular.auth.tokens import hash_token, new_token, tokens_match


def test_password_is_hashed_with_argon2id_and_verifies():
    hashed = hash_password("senha-bem-longa-1")
    assert hashed.startswith("$argon2id$")
    assert "senha-bem-longa-1" not in hashed
    assert verify_password("senha-bem-longa-1", hashed)
    assert not verify_password("senha-errada-123", hashed)


def test_same_password_gives_different_hashes():
    assert hash_password("senha-bem-longa-1") != hash_password("senha-bem-longa-1")


def test_weak_password_is_rejected():
    with pytest.raises(WeakPasswordError):
        hash_password("curta")


def test_invalid_hash_never_verifies():
    assert not verify_password("qualquer-coisa", "nao-e-um-hash")


def test_tokens_are_unique_and_compared_safely():
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 40
    assert len(hash_token(a)) == 64 and hash_token(a) != a
    assert tokens_match(a, a)
    assert not tokens_match(a, b)
    assert not tokens_match(None, a) and not tokens_match(a, "")
