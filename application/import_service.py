"""Importação assistida (seção 8.7):

    UPLOAD → DETECÇÃO → MAPEAMENTO → VALIDAÇÃO → PREVIEW → CONFIRMAÇÃO → IMPORTAÇÃO

O preview executa exatamente a mesma rotina da importação dentro de uma transação que é
desfeita no fim; o que o usuário confirma é o que foi mostrado.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from lipidence_modular.application.contracts import UserOut
from lipidence_modular.application.experimental_contracts import (
    DetectionOut,
    IdentityConflictOut,
    ImportBatchOut,
    ImportPreview,
    ImportReport,
    ManualReferenceIn,
    ManualSampleIn,
    ReportLine,
    SpectrumPreview,
    StagedImport,
    TemplateIn,
    TemplateOut,
)
from lipidence_modular.core.contracts import ArtifactStorage
from lipidence_modular.core.errors import (
    ConfigurationError,
    IdentityConflictError,
    LipidenceError,
)
from lipidence_modular.data.identity.normalization import normalize_sample_id
from lipidence_modular.data.identity.resolution import FieldOrigin
from lipidence_modular.data.importers.table import (
    ImportFileError,
    RawTable,
    extension_of,
    read_table,
)
from lipidence_modular.data.ingestion.plan import ImportKind, ImportPlan
from lipidence_modular.data.ingestion.reference import has_reference_columns, parse_reference
from lipidence_modular.data.ingestion.spectra import PlanError, detect_layout, parse_spectra
from lipidence_modular.data.mapping import roles
from lipidence_modular.data.reference.vocabulary import Vocabulary
from lipidence_modular.data.schemas.issues import IssueLog
from lipidence_modular.data.schemas.reference import ParsedReference
from lipidence_modular.data.schemas.spectral import (
    CANONICAL_AXIS_UNIT,
    SAMPLE_COLUMN_FIELDS,
    SAMPLE_FIELDS,
    ParsedSpectrum,
    axis_hash,
)
from lipidence_modular.repositories.database import session_scope
from lipidence_modular.repositories.experimental_repository import ExperimentalRepository
from lipidence_modular.storage.local import sha256_bytes

STAGED, IMPORTED = "STAGED", "IMPORTED"
PREVIEW_SPECTRA = 8
PREVIEW_ROWS = 5
PREVIEW_COLUMNS = 12


class ImportNotFoundError(LipidenceError):
    pass


class DuplicateImportError(LipidenceError):
    def __init__(self, existing_batch_id: str):
        self.existing_batch_id = existing_batch_id
        super().__init__(
            f"este arquivo já foi importado neste estudo (lote {existing_batch_id}); "
            "nada foi duplicado"
        )


class ImportStateError(LipidenceError):
    pass


def _detection_out(table: RawTable) -> DetectionOut:
    d = table.detection
    return DetectionOut(
        file_format=d.file_format, encoding=d.encoding, delimiter=d.delimiter,
        decimal=d.decimal, has_header=d.has_header, sheet=d.sheet, sheets=list(d.sheets),
    )


class ImportService:
    def __init__(self, session_factory: sessionmaker[Session], storage: ArtifactStorage,
                 vocabulary: Vocabulary):
        self._session_factory = session_factory
        self._storage = storage
        self._vocabulary = vocabulary

    @property
    def vocabulary(self) -> Vocabulary:
        return self._vocabulary

    # --- upload e detecção -------------------------------------------------------------
    def stage(self, *, content: bytes, filename: str, kind: ImportKind, study_id: str,
              user: UserOut) -> StagedImport:
        study_id = study_id.strip()
        if not study_id:
            raise PlanError("study_id é obrigatório")
        extension_of(filename)
        table = read_table(content, filename)
        file_hash = sha256_bytes(content)
        ref = self._storage.put_bytes(f"raw/{file_hash}/{filename}", content)
        with session_scope(self._session_factory) as db:
            repo = ExperimentalRepository(db)
            batch = repo.add_batch(
                kind=kind.value, study_id=study_id, status=STAGED, original_filename=filename,
                file_hash=file_hash, storage_key=ref.key, imported_by=user.id,
            )
            duplicate = repo.find_imported_batch(file_hash, kind.value, study_id, batch.id)
            return StagedImport(
                import_batch_id=batch.id, kind=kind, study_id=study_id,
                original_filename=filename, file_hash=file_hash,
                detection=_detection_out(table), columns=table.columns,
                suggested_columns=roles.suggest_mapping(
                    table.columns, table.detection.decimal, self._vocabulary,
                    table.detection.has_header,
                ),
                duplicate_of=duplicate.id if duplicate else None, notes=table.notes,
            )

    # --- preview e confirmação ---------------------------------------------------------
    def preview(self, import_batch_id: str, plan: ImportPlan, user: UserOut) -> ImportPreview:
        db = self._session_factory()
        try:
            repo = ExperimentalRepository(db)
            batch = self._staged_batch(repo, import_batch_id)
            duplicate = repo.find_imported_batch(
                batch.file_hash, batch.kind, batch.study_id, batch.id
            )
            base = {"import_batch_id": batch.id,
                    "duplicate_of": duplicate.id if duplicate else None}
            try:
                outcome = self._execute(repo, batch, plan, user)
            except IdentityConflictError as exc:
                return ImportPreview(
                    ok=False, blocking_error=str(exc),
                    conflict=IdentityConflictOut(field=exc.field, candidates=exc.candidates),
                    **base,
                )
            except (PlanError, ImportFileError, ConfigurationError) as exc:
                return ImportPreview(ok=False, blocking_error=str(exc), **base)
            return ImportPreview(ok=duplicate is None, **base, **outcome)
        finally:
            db.rollback()  # preview nunca grava
            db.close()

    def confirm(self, import_batch_id: str, plan: ImportPlan, user: UserOut) -> ImportReport:
        with session_scope(self._session_factory) as db:
            repo = ExperimentalRepository(db)
            batch = self._staged_batch(repo, import_batch_id)
            duplicate = repo.find_imported_batch(
                batch.file_hash, batch.kind, batch.study_id, batch.id
            )
            if duplicate is not None:
                raise DuplicateImportError(duplicate.id)
            outcome = self._execute(repo, batch, plan, user)
            report: ImportReport = outcome["report"]
            batch.status = IMPORTED
            batch.import_timestamp = datetime.now(UTC)
            batch.plan = plan.model_dump(mode="json")
            batch.report = report.model_dump(mode="json")
            return report

    def get_batch(self, import_batch_id: str) -> ImportBatchOut:
        with session_scope(self._session_factory) as db:
            batch = ExperimentalRepository(db).get_batch(import_batch_id)
            if batch is None:
                raise ImportNotFoundError(f"importação desconhecida: {import_batch_id}")
            return ImportBatchOut(
                import_batch_id=batch.id, kind=ImportKind(batch.kind), study_id=batch.study_id,
                status=batch.status, original_filename=batch.original_filename,
                file_hash=batch.file_hash, imported_by=batch.imported_by,
                import_timestamp=batch.import_timestamp,
                report=ImportReport(**batch.report) if batch.report else None,
            )

    @staticmethod
    def _staged_batch(repo: ExperimentalRepository, import_batch_id: str):
        batch = repo.get_batch(import_batch_id)
        if batch is None:
            raise ImportNotFoundError(f"importação desconhecida: {import_batch_id}")
        if batch.status != STAGED:
            raise ImportStateError(f"importação {import_batch_id} já foi confirmada")
        return batch

    # --- rotina única de preview e importação ------------------------------------------
    def _mapping(self, table: RawTable, plan: ImportPlan) -> dict[str, str]:
        suggested = roles.suggest_mapping(
            table.columns, table.detection.decimal, self._vocabulary, table.detection.has_header
        )
        if plan.columns is None:
            return suggested
        unknown = [c for c in plan.columns if c not in table.columns]
        if unknown:
            raise PlanError(f"colunas do mapeamento que não existem no arquivo: {unknown}")
        for role in plan.columns.values():
            roles.validate_role(role, self._vocabulary)
        # Coluna fora do mapeamento informado fica ignorada (e listada), nunca sugerida.
        return {c: plan.columns.get(c, roles.IGNORE) for c in table.columns}

    def _execute(self, repo: ExperimentalRepository, batch, plan: ImportPlan,
                 user: UserOut) -> dict:
        kind = ImportKind(batch.kind)
        content = self._storage.get_bytes(batch.storage_key)
        table = read_table(
            content, batch.original_filename, delimiter=plan.delimiter, decimal=plan.decimal,
            has_header=plan.has_header, sheet=plan.sheet,
        )
        mapping = self._mapping(table, plan)
        log = IssueLog()
        notes = list(table.notes)
        spectra: list[ParsedSpectrum] = []
        references: list[ParsedReference] = []
        layout = None
        if kind in (ImportKind.SPECTRA, ImportKind.COMBINED):
            layout = detect_layout(mapping).value
            spectra = parse_spectra(table, mapping, plan, batch.original_filename, log)
        if kind in (ImportKind.REFERENCE, ImportKind.COMBINED):
            references = parse_reference(table, mapping, plan, self._vocabulary, log)
        if kind is ImportKind.COMBINED and layout != "wide":
            raise PlanError("arquivo combinado exige layout largo (uma linha por amostra)")
        if kind is ImportKind.SPECTRA and has_reference_columns(mapping):
            notes.append("colunas de referência presentes foram ignoradas: para importá-las, "
                         "use o tipo 'arquivo combinado'")
        spectra = [s for s in spectra if not log.is_rejected(s.item)]
        references = [r for r in references if not log.is_rejected(r.item)]

        writer = _Writer(repo, batch, plan, user, log)
        for spectrum in spectra:
            writer.write_spectrum(spectrum)
        # No arquivo combinado, a linha cujo espectro foi rejeitado não entra pela metade.
        for reference in references:
            if not log.is_rejected(reference.item):
                writer.write_reference(reference)

        counts = log.counts()
        report = ImportReport(
            **counts,
            lines=[ReportLine(item=i.item, level=i.level.value, code=i.code, message=i.message)
                   for i in log.issues],
            spectra_written=writer.spectra_written,
            references_written=writer.references_written,
            samples_created=writer.samples_created, notes=notes,
        )
        head = [[("" if c is None else str(c)) for c in row[:PREVIEW_COLUMNS]]
                for row in table.rows[:PREVIEW_ROWS]]
        return {
            "detection": _detection_out(table),
            "columns": mapping,
            "ignored_columns": [c for c, r in mapping.items() if r == roles.IGNORE],
            "layout": layout,
            "head": head,
            "report": report,
            "spectra": [
                SpectrumPreview(sample_id=s.sample_id, axis_nm=s.axis_nm.tolist(),
                                values=s.values.tolist(), signal_type=s.signal_type.value)
                for s in spectra[:PREVIEW_SPECTRA]
            ],
        }

    # --- templates ---------------------------------------------------------------------
    def save_template(self, template: TemplateIn, user: UserOut) -> TemplateOut:
        for role in (template.plan.columns or {}).values():
            roles.validate_role(role, self._vocabulary)
        with session_scope(self._session_factory) as db:
            repo = ExperimentalRepository(db)
            if repo.get_template_by_name(template.name) is not None:
                raise LipidenceError(f"já existe template com o nome {template.name!r}")
            row = repo.add_template(
                name=template.name, kind=template.kind.value,
                plan=template.plan.model_dump(mode="json"), created_by=user.id,
            )
            return TemplateOut(id=row.id, **template.model_dump())

    def list_templates(self) -> list[TemplateOut]:
        with session_scope(self._session_factory) as db:
            return [
                TemplateOut(id=row.id, name=row.name, kind=ImportKind(row.kind),
                            plan=ImportPlan(**row.plan))
                for row in ExperimentalRepository(db).list_templates()
            ]

    # --- cadastro manual ---------------------------------------------------------------
    def register_sample(self, data: ManualSampleIn, user: UserOut) -> str:
        unknown = sorted(set(data.metadata) - set(SAMPLE_FIELDS))
        if unknown:
            raise PlanError(f"metadados desconhecidos: {unknown}. Aceitos: {list(SAMPLE_FIELDS)}")
        identity = normalize_sample_id(data.sample_id)
        with session_scope(self._session_factory) as db:
            repo = ExperimentalRepository(db)
            if repo.get_sample(data.study_id, identity.sample_id) is not None:
                raise LipidenceError(
                    f"amostra {identity.sample_id} já existe no estudo {data.study_id}"
                )
            metadata = {k: v.strip() for k, v in data.metadata.items() if v.strip()}
            repo.add_sample(
                study_id=data.study_id, sample_id=identity.sample_id,
                sample_id_raw=identity.sample_id_raw,
                sample_id_origin=FieldOrigin.USER_ENTERED.value, created_by=user.id,
                **_split_metadata(metadata),
                field_origins={k: FieldOrigin.USER_ENTERED.value for k in metadata},
            )
            return identity.sample_id

    def register_reference(self, data: ManualReferenceIn, user: UserOut) -> int:
        """Grava uma medida digitada. Devolve o número da replicata gravada."""
        identity = normalize_sample_id(data.sample_id)
        spec = self._vocabulary.resolve_parameter(data.parameter)
        if spec is None:
            raise PlanError(f"parâmetro fora do vocabulário: {data.parameter!r}")
        unit = self._vocabulary.resolve_unit(spec, data.unit)
        if unit is None:
            raise PlanError(
                f"{spec.name}: unidade desconhecida {data.unit!r} (aceitas: {list(spec.units)})"
            )
        with session_scope(self._session_factory) as db:
            repo = ExperimentalRepository(db)
            sample = repo.get_sample(data.study_id, identity.sample_id)
            if sample is None:
                raise LipidenceError(
                    f"amostra {identity.sample_id} não existe no estudo {data.study_id}"
                )
            existing = repo.reference_replicates(sample.id, spec.name)
            replicate = data.replicate
            if replicate is None:
                if existing:
                    raise PlanError(
                        f"{identity.sample_id} já tem medida de {spec.name}; informe a replicata"
                    )
                replicate = 1
            elif replicate in existing:
                raise PlanError(f"{identity.sample_id} / {spec.name}: replicata {replicate} "
                                "já existe")
            repo.add_reference(
                sample_pk=sample.id, parameter=spec.name, value=data.value, unit=unit,
                replicate=replicate, analysis_type=spec.analysis_type, method=data.method,
                analysis_date=data.date, laboratory=data.laboratory, created_by=user.id,
            )
            return replicate


def _split_metadata(metadata: dict[str, str]) -> dict:
    columns = {k: v for k, v in metadata.items() if k in SAMPLE_COLUMN_FIELDS}
    extra = {k: v for k, v in metadata.items() if k not in SAMPLE_COLUMN_FIELDS}
    return {**columns, "extra": extra}


class _Writer:
    """Grava espectros e referências de um lote, registrando alertas e rejeições de banco
    (amostra existente com metadado divergente, replicata já existente)."""

    def __init__(self, repo: ExperimentalRepository, batch, plan: ImportPlan, user: UserOut,
                 log: IssueLog):
        self.repo, self.batch, self.plan, self.user, self.log = repo, batch, plan, user, log
        self.spectra_written = self.references_written = self.samples_created = 0

    def _sample(self, item: str, sample_id: str, sample_id_raw: str, origin: FieldOrigin,
                metadata: dict[str, str], origins: dict[str, str]):
        sample = self.repo.get_sample(self.batch.study_id, sample_id)
        if sample is None:
            self.samples_created += 1
            return self.repo.add_sample(
                study_id=self.batch.study_id, sample_id=sample_id, sample_id_raw=sample_id_raw,
                sample_id_origin=origin.value, created_by=self.user.id,
                import_batch_id=self.batch.id, field_origins=dict(origins),
                **_split_metadata(metadata),
            )
        extra, field_origins = dict(sample.extra), dict(sample.field_origins)
        for name, value in metadata.items():
            current = getattr(sample, name) if name in SAMPLE_COLUMN_FIELDS else extra.get(name)
            if current in (None, ""):
                if name in SAMPLE_COLUMN_FIELDS:
                    setattr(sample, name, value)
                else:
                    extra[name] = value
                field_origins[name] = origins.get(name, FieldOrigin.FILE.value)
            elif current != value:
                self.log.alert(
                    item, "metadata_divergent",
                    f"{sample_id}: {name} diverge do cadastro (existente {current!r}, "
                    f"arquivo {value!r}); mantido o existente",
                )
        sample.extra, sample.field_origins = extra, field_origins
        return sample

    def _replicate(self, item: str, label: str, requested: int | None,
                   existing: list[int]) -> int | None:
        if requested is not None:
            if requested in existing:
                self.log.reject(item, "replicate_exists",
                                f"{label}: replicata {requested} já existe na base")
                return None
            return requested
        if not existing:
            return 1
        if not self.plan.repeated_rows_are_replicates:
            self.log.reject(
                item, "already_exists",
                f"{label}: já existe na base; para acrescentar como replicata, declare "
                "medidas repetidas como replicatas ou informe a coluna de replicata",
            )
            return None
        number = max(existing) + 1
        self.log.alert(item, "appended_replicate",
                       f"{label}: já existia na base; gravado como replicata {number}")
        return number

    def write_spectrum(self, spectrum: ParsedSpectrum) -> None:
        sample = self._sample(spectrum.item, spectrum.sample_id, spectrum.sample_id_raw,
                              spectrum.sample_id_origin, spectrum.sample_metadata,
                              spectrum.metadata_origins)
        replicate = self._replicate(
            spectrum.item, f"{spectrum.sample_id}: espectro", spectrum.technical_replicate,
            self.repo.spectrum_replicates(sample.id),
        )
        if replicate is None:
            return
        axis = self.repo.get_or_create_axis(
            axis_hash(spectrum.axis_nm), CANONICAL_AXIS_UNIT.value, spectrum.axis_nm.tolist()
        )
        metadata = dict(spectrum.spectrum_metadata)
        self.repo.add_spectrum(
            sample_pk=sample.id, axis_id=axis.id, technical_replicate=replicate,
            signal_type=spectrum.signal_type.value, values=spectrum.values.tolist(),
            instrument=metadata.pop("instrument", None), extra=metadata,
            provenance=list(spectrum.provenance), file_name=self.batch.original_filename,
            file_hash=self.batch.file_hash, import_batch_id=self.batch.id,
        )
        self.spectra_written += 1

    def write_reference(self, reference: ParsedReference) -> None:
        sample = self._sample(reference.item, reference.sample_id, reference.sample_id_raw,
                              reference.sample_id_origin, reference.sample_metadata,
                              reference.metadata_origins)
        replicate = self._replicate(
            reference.item, f"{reference.sample_id} / {reference.parameter}",
            reference.replicate, self.repo.reference_replicates(sample.id, reference.parameter),
        )
        if replicate is None:
            return
        self.repo.add_reference(
            sample_pk=sample.id, parameter=reference.parameter, value=reference.value,
            unit=reference.unit, replicate=replicate, analysis_type=reference.analysis_type,
            method=reference.method, analysis_date=reference.date,
            laboratory=reference.laboratory, import_batch_id=self.batch.id,
            created_by=self.user.id,
        )
        self.references_written += 1
