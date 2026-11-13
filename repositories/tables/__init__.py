"""Tabelas ORM. Importar este pacote registra todas as tabelas em ``Base.metadata``."""

from lipidence_modular.repositories.tables import auth, experimental  # noqa: F401
from lipidence_modular.repositories.tables.base import Base

__all__ = ["Base"]
