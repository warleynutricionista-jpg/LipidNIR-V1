"""Raiz de composição: liga configurações, banco, armazenamento, fila e serviços.

API, CLI e Dash recebem o mesmo ``AppContext``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from lipidence_modular.application.auth_service import AuthService
from lipidence_modular.application.experimental_base_service import ExperimentalBaseService
from lipidence_modular.application.import_service import ImportService
from lipidence_modular.core.config import Settings, load_settings
from lipidence_modular.core.contracts import ArtifactStorage, JobRunner
from lipidence_modular.data.reference.vocabulary import default_vocabulary
from lipidence_modular.jobs.in_process import InProcessJobRunner
from lipidence_modular.repositories.database import make_engine, make_session_factory
from lipidence_modular.storage.local import LocalArtifactStorage


@dataclass
class AppContext:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    storage: ArtifactStorage
    jobs: JobRunner
    auth: AuthService
    imports: ImportService
    base: ExperimentalBaseService

    def close(self) -> None:
        self.jobs.shutdown()
        self.engine.dispose()


def build_context(settings: Settings | None = None) -> AppContext:
    settings = settings or load_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    storage = LocalArtifactStorage(settings.storage_dir)
    return AppContext(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        storage=storage,
        jobs=InProcessJobRunner(),
        auth=AuthService(session_factory, settings),
        imports=ImportService(session_factory, storage, default_vocabulary()),
        base=ExperimentalBaseService(session_factory),
    )
