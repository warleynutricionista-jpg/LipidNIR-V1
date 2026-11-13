"""Engine e fábrica de sessões SQLAlchemy."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from lipidence_modular.core.errors import ConfigurationError


def make_engine(database_url: str) -> Engine:
    if not database_url.startswith("postgresql"):
        raise ConfigurationError(
            "o banco da aplicação é PostgreSQL; URL recebida não começa com 'postgresql'"
        )
    return create_engine(database_url, pool_pre_ping=True, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transação por unidade de trabalho: commit no fim, rollback em erro."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
