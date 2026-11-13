"""Consulta objetiva da base experimental (seção 19.3)."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from lipidence_modular.application.experimental_contracts import (
    BaseSummary,
    FilterOptions,
    SampleFilters,
    SampleList,
    SampleOut,
)
from lipidence_modular.core.errors import ConfigurationError
from lipidence_modular.repositories.database import session_scope
from lipidence_modular.repositories.experimental_repository import (
    COMPLETENESS_FILTERS,
    ExperimentalRepository,
)


class ExperimentalBaseService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def summary(self, study_id: str | None = None) -> BaseSummary:
        with session_scope(self._session_factory) as db:
            return BaseSummary(**ExperimentalRepository(db).summary(study_id))

    def filter_options(self) -> FilterOptions:
        with session_scope(self._session_factory) as db:
            repo = ExperimentalRepository(db)
            return FilterOptions(
                studies=repo.distinct_values("study_id"),
                genotypes=repo.distinct_values("genotype"),
                batches=repo.distinct_values("batch"), lots=repo.distinct_values("lot"),
            )

    def list_samples(self, filters: SampleFilters) -> SampleList:
        if filters.completeness is not None and filters.completeness not in COMPLETENESS_FILTERS:
            raise ConfigurationError(
                f"filtro de completude desconhecido: {filters.completeness!r}. "
                f"Aceitos: {list(COMPLETENESS_FILTERS)}"
            )
        with session_scope(self._session_factory) as db:
            total, rows = ExperimentalRepository(db).list_samples(**filters.model_dump())
            samples = []
            for sample, n_spectra, parameters in rows:
                parameters = sorted(parameters or [])
                samples.append(SampleOut(
                    study_id=sample.study_id, sample_id=sample.sample_id,
                    sample_id_raw=sample.sample_id_raw,
                    sample_id_origin=sample.sample_id_origin, genotype=sample.genotype,
                    cultivar=sample.cultivar, batch=sample.batch, lot=sample.lot,
                    matrix=sample.matrix, storage_time=sample.storage_time,
                    storage_condition=sample.storage_condition, extra=sample.extra,
                    n_spectra=n_spectra, parameters=parameters,
                    complete=n_spectra > 0 and bool(parameters),
                ))
            return SampleList(total=total, samples=samples)
