"""Repositório da base experimental."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lipidence_modular.repositories.tables.experimental import (
    ImportBatchRow,
    MappingTemplateRow,
    ReferenceAnalysisRow,
    SampleRow,
    SpectralAxisRow,
    SpectrumRow,
)

COMPLETENESS_FILTERS = ("complete", "incomplete", "no_spectrum", "no_reference")


class ExperimentalRepository:
    def __init__(self, session: Session):
        self.session = session

    # --- importações -------------------------------------------------------------------
    def add_batch(self, **fields) -> ImportBatchRow:
        row = ImportBatchRow(**fields)
        self.session.add(row)
        self.session.flush()
        return row

    def get_batch(self, batch_id: str) -> ImportBatchRow | None:
        return self.session.get(ImportBatchRow, batch_id)

    def find_imported_batch(
        self, file_hash: str, kind: str, study_id: str, exclude_id: str
    ) -> ImportBatchRow | None:
        return self.session.scalar(
            select(ImportBatchRow)
            .where(
                ImportBatchRow.file_hash == file_hash,
                ImportBatchRow.kind == kind,
                ImportBatchRow.study_id == study_id,
                ImportBatchRow.status == "IMPORTED",
                ImportBatchRow.id != exclude_id,
            )
            .limit(1)
        )

    # --- templates ---------------------------------------------------------------------
    def add_template(self, **fields) -> MappingTemplateRow:
        row = MappingTemplateRow(**fields)
        self.session.add(row)
        self.session.flush()
        return row

    def get_template_by_name(self, name: str) -> MappingTemplateRow | None:
        return self.session.scalar(
            select(MappingTemplateRow).where(MappingTemplateRow.name == name)
        )

    def list_templates(self) -> list[MappingTemplateRow]:
        return list(
            self.session.scalars(select(MappingTemplateRow).order_by(MappingTemplateRow.name))
        )

    # --- amostras ----------------------------------------------------------------------
    def get_sample(self, study_id: str, sample_id: str) -> SampleRow | None:
        return self.session.scalar(
            select(SampleRow).where(
                SampleRow.study_id == study_id, SampleRow.sample_id == sample_id
            )
        )

    def add_sample(self, **fields) -> SampleRow:
        row = SampleRow(**fields)
        self.session.add(row)
        self.session.flush()
        return row

    # --- espectros ---------------------------------------------------------------------
    def get_or_create_axis(self, axis_hash: str, unit: str, values: list[float]):
        row = self.session.scalar(
            select(SpectralAxisRow).where(SpectralAxisRow.axis_hash == axis_hash)
        )
        if row is None:
            row = SpectralAxisRow(
                axis_hash=axis_hash, unit=unit, n_points=len(values), values=values
            )
            self.session.add(row)
            self.session.flush()
        return row

    def spectrum_replicates(self, sample_pk: str) -> list[int]:
        return list(
            self.session.scalars(
                select(SpectrumRow.technical_replicate).where(
                    SpectrumRow.sample_pk == sample_pk
                )
            )
        )

    def add_spectrum(self, **fields) -> SpectrumRow:
        row = SpectrumRow(**fields)
        self.session.add(row)
        self.session.flush()
        return row

    # --- referências -------------------------------------------------------------------
    def reference_replicates(self, sample_pk: str, parameter: str) -> list[int]:
        return list(
            self.session.scalars(
                select(ReferenceAnalysisRow.replicate).where(
                    ReferenceAnalysisRow.sample_pk == sample_pk,
                    ReferenceAnalysisRow.parameter == parameter,
                )
            )
        )

    def add_reference(self, **fields) -> ReferenceAnalysisRow:
        row = ReferenceAnalysisRow(**fields)
        self.session.add(row)
        self.session.flush()
        return row

    # --- consulta ----------------------------------------------------------------------
    def summary(self, study_id: str | None = None) -> dict[str, int]:
        has_spectrum = select(SpectrumRow.sample_pk).distinct()
        has_reference = select(ReferenceAnalysisRow.sample_pk).distinct()

        def count(stmt):
            if study_id:
                stmt = stmt.where(SampleRow.study_id == study_id)
            return int(self.session.scalar(stmt) or 0)

        base = select(func.count()).select_from(SampleRow)
        with_spectrum = base.where(SampleRow.id.in_(has_spectrum))
        with_reference = base.where(SampleRow.id.in_(has_reference))
        spectra = (
            select(func.count())
            .select_from(SpectrumRow)
            .join(SampleRow, SampleRow.id == SpectrumRow.sample_pk)
        )
        return {
            "samples": count(base),
            "samples_with_spectrum": count(with_spectrum),
            "samples_with_reference": count(with_reference),
            "complete_samples": count(with_spectrum.where(SampleRow.id.in_(has_reference))),
            "spectra": count(spectra),
        }

    def list_samples(
        self,
        *,
        study_id: str | None = None,
        genotype: str | None = None,
        batch: str | None = None,
        lot: str | None = None,
        completeness: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ):
        n_spectra = (
            select(func.count())
            .select_from(SpectrumRow)
            .where(SpectrumRow.sample_pk == SampleRow.id)
            .correlate(SampleRow)
            .scalar_subquery()
        )
        parameters = (
            select(func.array_agg(func.distinct(ReferenceAnalysisRow.parameter)))
            .where(ReferenceAnalysisRow.sample_pk == SampleRow.id)
            .correlate(SampleRow)
            .scalar_subquery()
        )
        stmt = select(SampleRow, n_spectra.label("n_spectra"), parameters.label("parameters"))
        for column, value in (
            (SampleRow.study_id, study_id),
            (SampleRow.genotype, genotype),
            (SampleRow.batch, batch),
            (SampleRow.lot, lot),
        ):
            if value:
                stmt = stmt.where(column == value)
        has_ref = (
            select(ReferenceAnalysisRow.id)
            .where(ReferenceAnalysisRow.sample_pk == SampleRow.id)
            .exists()
        )
        has_spec = select(SpectrumRow.id).where(SpectrumRow.sample_pk == SampleRow.id).exists()
        if completeness == "complete":
            stmt = stmt.where(has_ref, has_spec)
        elif completeness == "incomplete":
            stmt = stmt.where(~(has_ref & has_spec))
        elif completeness == "no_spectrum":
            stmt = stmt.where(~has_spec)
        elif completeness == "no_reference":
            stmt = stmt.where(~has_ref)
        elif completeness is not None:
            raise ValueError(f"filtro de completude desconhecido: {completeness!r}")
        total = int(self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        rows = self.session.execute(
            stmt.order_by(SampleRow.study_id, SampleRow.sample_id).limit(limit).offset(offset)
        ).all()
        return total, rows

    def distinct_values(self, column_name: str) -> list[str]:
        column = getattr(SampleRow, column_name)
        return list(
            self.session.scalars(
                select(column).where(column.is_not(None)).distinct().order_by(column)
            )
        )
