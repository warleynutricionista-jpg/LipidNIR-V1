"""Repositório de usuários e sessões."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lipidence_modular.repositories.tables.auth import SessionRow, UserRow


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_username(self, username: str) -> UserRow | None:
        return self.session.scalar(select(UserRow).where(UserRow.username == username))

    def get_user(self, user_id: str) -> UserRow | None:
        return self.session.get(UserRow, user_id)

    def add_user(self, username: str, password_hash: str, role: str) -> UserRow:
        row = UserRow(username=username, password_hash=password_hash, role=role)
        self.session.add(row)
        self.session.flush()
        return row

    def count_users(self, role: str | None = None) -> int:
        stmt = select(func.count()).select_from(UserRow)
        if role is not None:
            stmt = stmt.where(UserRow.role == role)
        return int(self.session.scalar(stmt) or 0)

    def add_session(
        self, user_id: str, token_hash: str, csrf_token: str, expires_at: datetime
    ) -> SessionRow:
        row = SessionRow(
            user_id=user_id, token_hash=token_hash, csrf_token=csrf_token, expires_at=expires_at
        )
        self.session.add(row)
        self.session.flush()
        return row

    def get_session_by_token_hash(self, token_hash: str) -> SessionRow | None:
        return self.session.scalar(select(SessionRow).where(SessionRow.token_hash == token_hash))
