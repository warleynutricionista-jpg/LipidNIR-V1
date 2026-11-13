"""Caso de uso de autenticação: login, sessão, logout e criação de usuário."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from lipidence_modular.application.contracts import (
    AuthenticatedSession,
    CreateUserInput,
    LoginResult,
    UserOut,
)
from lipidence_modular.auth.passwords import DUMMY_HASH, hash_password, verify_password
from lipidence_modular.auth.roles import Role
from lipidence_modular.auth.tokens import hash_token, new_token
from lipidence_modular.core.config import Settings
from lipidence_modular.core.errors import LipidenceError
from lipidence_modular.repositories.auth_repository import AuthRepository
from lipidence_modular.repositories.database import session_scope


class InvalidCredentialsError(LipidenceError):
    """Usuário ou senha inválidos (mensagem única, sem revelar qual dos dois)."""


class UserAlreadyExistsError(LipidenceError):
    pass


class PermissionDeniedError(LipidenceError):
    pass


def normalize_username(username: str) -> str:
    return username.strip().lower()


class AuthService:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings):
        self._session_factory = session_factory
        self._settings = settings

    def create_user(self, data: CreateUserInput) -> UserOut:
        username = normalize_username(data.username)
        password_hash = hash_password(data.password)
        with session_scope(self._session_factory) as db:
            repo = AuthRepository(db)
            if repo.get_user_by_username(username) is not None:
                raise UserAlreadyExistsError(f"usuário já existe: {username}")
            row = repo.add_user(username, password_hash, data.role.value)
            return UserOut(id=row.id, username=row.username, role=Role(row.role))

    def get_user(self, username: str) -> UserOut:
        with session_scope(self._session_factory) as db:
            row = AuthRepository(db).get_user_by_username(normalize_username(username))
            if row is None or not row.is_active:
                raise LipidenceError(f"usuário inexistente ou inativo: {username}")
            return UserOut(id=row.id, username=row.username, role=Role(row.role))

    def login(self, username: str, password: str) -> LoginResult:
        username = normalize_username(username)
        with session_scope(self._session_factory) as db:
            repo = AuthRepository(db)
            user = repo.get_user_by_username(username)
            if user is None or not user.is_active:
                verify_password(password, DUMMY_HASH)
                raise InvalidCredentialsError("usuário ou senha inválidos")
            if not verify_password(password, user.password_hash):
                raise InvalidCredentialsError("usuário ou senha inválidos")
            token, csrf = new_token(), new_token()
            expires = datetime.now(UTC) + timedelta(minutes=self._settings.session_ttl_minutes)
            repo.add_session(user.id, hash_token(token), csrf, expires)
            return LoginResult(
                token=token,
                session=AuthenticatedSession(
                    user=UserOut(id=user.id, username=user.username, role=Role(user.role)),
                    csrf_token=csrf,
                    expires_at=expires,
                ),
            )

    def resolve(self, token: str | None) -> AuthenticatedSession | None:
        """Sessão válida para o token, ou ``None`` (ausente, expirada ou revogada)."""
        if not token:
            return None
        with session_scope(self._session_factory) as db:
            repo = AuthRepository(db)
            row = repo.get_session_by_token_hash(hash_token(token))
            if row is None or row.revoked_at is not None:
                return None
            if row.expires_at <= datetime.now(UTC):
                return None
            user = repo.get_user(row.user_id)
            if user is None or not user.is_active:
                return None
            return AuthenticatedSession(
                user=UserOut(id=user.id, username=user.username, role=Role(user.role)),
                csrf_token=row.csrf_token,
                expires_at=row.expires_at,
            )

    def logout(self, token: str | None) -> bool:
        if not token:
            return False
        with session_scope(self._session_factory) as db:
            row = AuthRepository(db).get_session_by_token_hash(hash_token(token))
            if row is None or row.revoked_at is not None:
                return False
            row.revoked_at = datetime.now(UTC)
            return True

    @staticmethod
    def require_role(session: AuthenticatedSession, role: Role) -> None:
        if session.user.role != role:
            raise PermissionDeniedError(f"ação restrita ao papel {role.value}")
