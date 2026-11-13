"""Fixtures comuns.

Testes marcados ``db`` precisam de PostgreSQL em ``LIPIDENCE_TEST_DATABASE_URL``. Sem a
variável, são pulados com motivo explícito; com ``LIPIDENCE_REQUIRE_DB=1`` (CI), a ausência
é erro, para que o CI nunca passe sem exercitar o banco.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from lipidence_modular.application.context import build_context
from lipidence_modular.core.config import Settings
from lipidence_modular.repositories import migrate
from lipidence_modular.repositories.database import make_engine

DB_ENV = "LIPIDENCE_TEST_DATABASE_URL"


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get(DB_ENV, "").strip()
    if not url:
        if os.environ.get("LIPIDENCE_REQUIRE_DB") == "1":
            pytest.fail(f"{DB_ENV} não definido e LIPIDENCE_REQUIRE_DB=1")
        pytest.skip(f"PostgreSQL de teste não configurado ({DB_ENV})")
    return url


def reset_schema(url: str) -> None:
    engine = make_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


@pytest.fixture()
def clean_database(database_url) -> str:
    """Banco vazio, sem nenhuma tabela."""
    reset_schema(database_url)
    return database_url


@pytest.fixture()
def migrated_database(clean_database) -> str:
    migrate.upgrade(clean_database)
    return clean_database


@pytest.fixture()
def settings(migrated_database, tmp_path) -> Settings:
    return Settings(
        database_url=migrated_database, storage_dir=tmp_path / "artifacts", environment="test"
    )


@pytest.fixture()
def context(settings):
    ctx = build_context(settings)
    yield ctx
    ctx.close()
