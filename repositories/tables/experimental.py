"""Base experimental: amostras, espectros, análises de referência, importações (seção 18)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lipidence_modular.repositories.tables.base import Base, new_id, utcnow


class ImportBatchRow(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    study_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # STAGED | IMPORTED
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    imported_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    import_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    template_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("mapping_templates.id"), nullable=True
    )
    plan: Mapped[dict | None] = mapped_column(JSONB)
    report: Mapped[dict | None] = mapped_column(JSONB)


class MappingTemplateRow(Base):
    __tablename__ = "mapping_templates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class SampleRow(Base):
    __tablename__ = "samples"
    __table_args__ = (UniqueConstraint("study_id", "sample_id", name="uq_samples_study_sample"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    study_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sample_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sample_id_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    sample_id_origin: Mapped[str] = mapped_column(String(16), nullable=False)
    genotype: Mapped[str | None] = mapped_column(String(128), index=True)
    cultivar: Mapped[str | None] = mapped_column(String(128))
    batch: Mapped[str | None] = mapped_column(String(128), index=True)
    lot: Mapped[str | None] = mapped_column(String(128), index=True)
    matrix: Mapped[str | None] = mapped_column(String(128))
    storage_time: Mapped[str | None] = mapped_column(String(64))
    storage_condition: Mapped[str | None] = mapped_column(String(128))
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    field_origins: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    import_batch_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("import_batches.id"), nullable=True
    )


class SpectralAxisRow(Base):
    __tablename__ = "spectral_axes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    axis_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    n_points: Mapped[int] = mapped_column(Integer, nullable=False)
    values: Mapped[list[float]] = mapped_column(ARRAY(Float(53)), nullable=False)


class SpectrumRow(Base):
    __tablename__ = "spectra"
    __table_args__ = (
        UniqueConstraint("sample_pk", "technical_replicate", name="uq_spectra_sample_replicate"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sample_pk: Mapped[str] = mapped_column(
        String(32), ForeignKey("samples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    axis_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("spectral_axes.id"), nullable=False
    )
    technical_replicate: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    values: Mapped[list[float]] = mapped_column(ARRAY(Float(53)), nullable=False)
    instrument: Mapped[str | None] = mapped_column(String(128))
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    provenance: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    import_batch_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("import_batches.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class ReferenceAnalysisRow(Base):
    """Uma linha por amostra × parâmetro × replicata."""

    __tablename__ = "reference_analyses"
    __table_args__ = (
        UniqueConstraint(
            "sample_pk", "parameter", "replicate", name="uq_reference_sample_parameter_replicate"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sample_pk: Mapped[str] = mapped_column(
        String(32), ForeignKey("samples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float(53), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    replicate: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_type: Mapped[str | None] = mapped_column(String(64))
    method: Mapped[str | None] = mapped_column(String(128))
    analysis_date: Mapped[str | None] = mapped_column(String(32))
    laboratory: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    import_batch_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("import_batches.id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
