"""Contratos Pydantic de entrada e saída (os mesmos para API, CLI e Dash)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from lipidence_modular.auth.roles import Role


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UserOut(Contract):
    id: str
    username: str
    role: Role


class AuthenticatedSession(Contract):
    user: UserOut
    csrf_token: str
    expires_at: datetime


class LoginResult(Contract):
    token: str = Field(repr=False)
    session: AuthenticatedSession


class CreateUserInput(Contract):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(repr=False)
    role: Role
