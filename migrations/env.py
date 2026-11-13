"""Ambiente Alembic. A URL vem da configuração montada em ``repositories/migrate.py``."""

from alembic import context
from sqlalchemy import create_engine

from lipidence_modular.repositories.tables import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(context.config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("modo offline do Alembic não é suportado nesta aplicação")
run_migrations_online()
