"""Contratos da base experimental: importação, relatório, consulta e cadastro manual."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from lipidence_modular.application.contracts import Contract
from lipidence_modular.data.ingestion.plan import ImportKind, ImportPlan


class DetectionOut(Contract):
    file_format: str
    encoding: str | None
    delimiter: str | None
    decimal: str
    has_header: bool
    sheet: str | None
    sheets: list[str]


class StagedImport(Contract):
    import_batch_id: str
    kind: ImportKind
    study_id: str
    original_filename: str
    file_hash: str
    detection: DetectionOut
    columns: list[str]
    suggested_columns: dict[str, str]
    duplicate_of: str | None = None
    notes: list[str] = Field(default_factory=list)


class ReportLine(Contract):
    item: str
    level: str
    code: str
    message: str


class ImportReport(Contract):
    """Contagens mutuamente exclusivas: received = imported + alerts + rejected."""

    received: int
    imported: int
    alerts: int
    rejected: int
    lines: list[ReportLine]
    spectra_written: int
    references_written: int
    samples_created: int
    notes: list[str] = Field(default_factory=list)

    def as_text(self) -> str:
        head = (f"Arquivos recebidos: {self.received}      Importados: {self.imported}      "
                f"Alertas: {self.alerts}      Rejeitados: {self.rejected}")
        body = [f"{line.item} → {line.message}" for line in self.lines]
        return "\n".join([head, "", *body]) if body else head


class IdentityConflictOut(Contract):
    field: str
    candidates: dict[str, str]


class SpectrumPreview(Contract):
    sample_id: str
    axis_nm: list[float]
    values: list[float]
    signal_type: str


class ImportPreview(Contract):
    import_batch_id: str
    ok: bool
    blocking_error: str | None = None
    conflict: IdentityConflictOut | None = None
    duplicate_of: str | None = None
    detection: DetectionOut | None = None
    columns: dict[str, str] = Field(default_factory=dict)
    ignored_columns: list[str] = Field(default_factory=list)
    layout: str | None = None
    head: list[list[str]] = Field(default_factory=list)
    report: ImportReport | None = None
    spectra: list[SpectrumPreview] = Field(default_factory=list)


class ImportBatchOut(Contract):
    import_batch_id: str
    kind: ImportKind
    study_id: str
    status: str
    original_filename: str
    file_hash: str
    imported_by: str
    import_timestamp: datetime | None
    report: ImportReport | None


class TemplateIn(Contract):
    name: str = Field(min_length=1, max_length=128)
    kind: ImportKind
    plan: ImportPlan


class TemplateOut(TemplateIn):
    id: str


class BaseSummary(Contract):
    samples: int
    samples_with_spectrum: int
    samples_with_reference: int
    complete_samples: int
    spectra: int


class SampleOut(Contract):
    study_id: str
    sample_id: str
    sample_id_raw: str
    sample_id_origin: str
    genotype: str | None
    cultivar: str | None
    batch: str | None
    lot: str | None
    matrix: str | None
    storage_time: str | None
    storage_condition: str | None
    extra: dict[str, str]
    n_spectra: int
    parameters: list[str]
    complete: bool


class SampleList(Contract):
    total: int
    samples: list[SampleOut]


class SampleFilters(Contract):
    study_id: str | None = None
    genotype: str | None = None
    batch: str | None = None
    lot: str | None = None
    completeness: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class FilterOptions(Contract):
    studies: list[str]
    genotypes: list[str]
    batches: list[str]
    lots: list[str]


class ManualSampleIn(Contract):
    study_id: str = Field(min_length=1, max_length=128)
    sample_id: str
    metadata: dict[str, str] = Field(default_factory=dict)


class ManualReferenceIn(Contract):
    study_id: str = Field(min_length=1, max_length=128)
    sample_id: str
    parameter: str
    value: float
    unit: str
    replicate: int | None = Field(default=None, ge=1)
    method: str | None = None
    date: str | None = None
    laboratory: str | None = None
