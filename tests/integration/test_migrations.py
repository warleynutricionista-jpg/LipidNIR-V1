import pytest
from sqlalchemy import inspect

from lipidence_modular.repositories import migrate
from lipidence_modular.repositories.database import make_engine
from lipidence_modular.repositories.tables import Base

pytestmark = pytest.mark.db


def test_migrations_apply_from_zero_and_reach_head(clean_database):
    engine = make_engine(clean_database)
    try:
        assert inspect(engine).get_table_names() == []
        migrate.upgrade(clean_database)
        assert migrate.current_revision(engine) == migrate.head_revision(clean_database)
    finally:
        engine.dispose()


def test_migrated_schema_matches_orm_metadata(migrated_database):
    """Toda tabela e coluna do ORM existe no banco migrado, e nada além delas."""
    engine = make_engine(migrated_database)
    try:
        inspector = inspect(engine)
        db_tables = set(inspector.get_table_names()) - {"alembic_version"}
        assert db_tables == set(Base.metadata.tables)
        for name, table in Base.metadata.tables.items():
            db_columns = {c["name"]: c for c in inspector.get_columns(name)}
            assert set(db_columns) == {c.name for c in table.columns}, name
            for column in table.columns:
                assert db_columns[column.name]["nullable"] == column.nullable, (name, column.name)
    finally:
        engine.dispose()


def test_downgrade_to_base_removes_everything(migrated_database):
    migrate.downgrade(migrated_database, "base")
    engine = make_engine(migrated_database)
    try:
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()
