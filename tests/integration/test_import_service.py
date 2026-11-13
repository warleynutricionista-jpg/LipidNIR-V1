"""Importação assistida de ponta a ponta no serviço (seções 8.7 e 20)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from lipidence_modular.application.contracts import CreateUserInput
from lipidence_modular.application.experimental_contracts import (
    ManualReferenceIn,
    ManualSampleIn,
    SampleFilters,
    TemplateIn,
)
from lipidence_modular.application.import_service import DuplicateImportError, ImportStateError
from lipidence_modular.auth.roles import Role
from lipidence_modular.core.errors import ConfigurationError, IdentityConflictError, LipidenceError
from lipidence_modular.data.ingestion.plan import ImportKind, ImportPlan
from lipidence_modular.data.ingestion.spectra import PlanError
from lipidence_modular.repositories.database import session_scope
from lipidence_modular.repositories.tables.experimental import (
    ReferenceAnalysisRow,
    SampleRow,
    SpectralAxisRow,
    SpectrumRow,
)
from lipidence_modular.tests.fixtures import synthetic

pytestmark = pytest.mark.db

PLAN = ImportPlan(signal_type="absorbance", wavelength_unit="nm")
DATA = synthetic.make_set(3, 2, seed=1)


@pytest.fixture()
def user(context):
    return context.auth.create_user(
        CreateUserInput(username="ana", password="senha-de-teste-123", role=Role.USER))


def count(context, table, *where):
    with session_scope(context.session_factory) as db:
        return db.scalar(select(func.count()).select_from(table).where(*where))


def do_import(context, user, content, name, kind, plan=PLAN, study="E1"):
    staged = context.imports.stage(
        content=content, filename=name, kind=kind, study_id=study, user=user)
    return staged, context.imports.confirm(staged.import_batch_id, plan, user)


def test_stage_stores_raw_file_with_hash_and_suggests_mapping(context, user):
    content = synthetic.wide_csv(DATA)
    staged = context.imports.stage(content=content, filename="nir.csv",
                                   kind=ImportKind.SPECTRA, study_id="E1", user=user)
    assert staged.detection.delimiter == ";" and staged.detection.decimal == ","
    assert staged.suggested_columns["Sample"] == "sample_id"
    assert context.storage.get_bytes(f"raw/{staged.file_hash}/nir.csv") == content
    batch = context.imports.get_batch(staged.import_batch_id)
    assert (batch.status, batch.imported_by, batch.report) == ("STAGED", user.id, None)
    assert count(context, SampleRow) == 0  # upload não importa nada


def test_preview_shows_what_would_happen_and_writes_nothing(context, user):
    staged = context.imports.stage(content=synthetic.wide_csv(DATA), filename="nir.csv",
                                   kind=ImportKind.SPECTRA, study_id="E1", user=user)
    preview = context.imports.preview(staged.import_batch_id, PLAN, user)
    assert preview.ok and preview.layout == "wide"
    assert preview.report.received == 6 and preview.report.spectra_written == 6
    assert len(preview.spectra) == 6 and preview.spectra[0].sample_id == "S001"
    assert len(preview.head) == 5
    assert count(context, SampleRow) == 0 and count(context, SpectrumRow) == 0
    assert context.imports.get_batch(staged.import_batch_id).status == "STAGED"


def test_preview_reports_blocking_plan_error_instead_of_guessing(context, user):
    staged = context.imports.stage(content=synthetic.wide_csv(DATA), filename="nir.csv",
                                   kind=ImportKind.SPECTRA, study_id="E1", user=user)
    preview = context.imports.preview(staged.import_batch_id, ImportPlan(), user)
    assert not preview.ok and "signal_type" in preview.blocking_error
    with pytest.raises(PlanError):
        context.imports.confirm(staged.import_batch_id, ImportPlan(), user)
    assert count(context, SampleRow) == 0


def test_imports_the_three_spectral_layouts(context, user):
    _, wide = do_import(context, user, synthetic.wide_csv(DATA), "w.csv", ImportKind.SPECTRA)
    assert (wide.received, wide.imported, wide.spectra_written) == (6, 6, 6)
    _, long = do_import(context, user, synthetic.long_csv(DATA), "l.csv", ImportKind.SPECTRA,
                        study="E2")
    assert (long.received, long.imported, long.spectra_written) == (6, 6, 6)
    single_plan = PLAN.model_copy(update={"user_sample_id": "S001"})
    _, single = do_import(context, user, synthetic.single_txt(DATA, 0), "S001.txt",
                          ImportKind.SPECTRA, single_plan, study="E3")
    assert (single.received, single.imported, single.spectra_written) == (1, 1, 1)
    assert count(context, SpectrumRow) == 13
    assert count(context, SpectralAxisRow) == 1  # eixo compartilhado pelo hash
    with session_scope(context.session_factory) as db:
        row = db.scalar(select(SpectrumRow).limit(1))
        assert row.file_hash and row.file_name and row.signal_type == "absorbance"
        sample = db.scalar(select(SampleRow).where(SampleRow.study_id == "E1").limit(1))
        assert sample.genotype and sample.field_origins == {"genotype": "FILE"}
        assert sample.sample_id_origin == "FILE" and sample.created_by == user.id


def test_combined_file_imports_spectra_metadata_and_references(context, user):
    staged, report = do_import(context, user, synthetic.wide_csv(DATA, references=True),
                               "combinado.csv", ImportKind.COMBINED)
    assert (report.received, report.imported, report.alerts, report.rejected) == (6, 6, 0, 0)
    assert (report.spectra_written, report.references_written, report.samples_created) == (
        6, 12, 6)
    summary = context.base.summary()
    assert summary.model_dump() == {
        "samples": 6, "samples_with_spectrum": 6, "samples_with_reference": 6,
        "complete_samples": 6, "spectra": 6}
    batch = context.imports.get_batch(staged.import_batch_id)
    assert batch.status == "IMPORTED" and batch.report.received == 6
    assert batch.import_timestamp is not None


def test_identity_links_spectrum_and_reference_only_by_exact_sample_id(context, user):
    """Seção 20: espectro A001 + cromatografia A001 se associam; A001 + A002 não."""
    two = synthetic.make_set(1, 2, seed=5)
    two.sample_ids = ["A001", "A003"]
    do_import(context, user, synthetic.wide_csv(two), "nir.csv", ImportKind.SPECTRA)
    refs = synthetic.reference_long_csv(two, sample_ids=[" a001 ", "A002"])
    _, report = do_import(context, user, refs, "gc.csv", ImportKind.REFERENCE, ImportPlan())
    assert report.references_written == 4
    listed = {s.sample_id: s for s in context.base.list_samples(SampleFilters()).samples}
    assert set(listed) == {"A001", "A002", "A003"}
    assert listed["A001"].complete and listed["A001"].parameters == ["C18:2", "TBARS"]
    assert not listed["A002"].complete and listed["A002"].n_spectra == 0  # sem espectro
    assert not listed["A003"].complete and listed["A003"].parameters == []  # sem referência
    assert context.base.summary().complete_samples == 1


def test_report_counts_and_lines_follow_section_8_7(context, user):
    text = synthetic.wide_csv(DATA, references=True).decode().splitlines()
    cells = text[2].split(";")
    cells[30] = ""                       # S002: espectro incompleto
    text[2] = ";".join(cells)
    cells = text[3].split(";")
    cells[-2] = "140,0"                  # S003: C18:2 fora da faixa plausível (alerta)
    text[3] = ";".join(cells)
    text[4] = text[4].replace("S004", "S001", 1)  # sample_id duplicado (S001 duas vezes)
    _, report = do_import(context, user, "\n".join(text).encode(), "c.csv",
                          ImportKind.COMBINED)
    assert (report.received, report.imported, report.alerts, report.rejected) == (6, 2, 1, 3)
    assert report.received == report.imported + report.alerts + report.rejected
    assert (report.spectra_written, report.references_written) == (3, 6)
    rendered = report.as_text()
    assert rendered.startswith(
        "Arquivos recebidos: 6      Importados: 2      Alertas: 1      Rejeitados: 3")
    assert "→ S001: sample_id duplicado" in rendered
    assert "espectro incompleto" in rendered and "faixa plausível" in rendered
    # Linha rejeitada não entra pela metade: S002 não tem espectro nem referência.
    assert {s.sample_id for s in context.base.list_samples(SampleFilters()).samples} == {
        "S003", "S005", "S006"}


def test_reimporting_the_same_file_warns_and_does_not_duplicate(context, user):
    content = synthetic.wide_csv(DATA)
    first, _ = do_import(context, user, content, "nir.csv", ImportKind.SPECTRA)
    again = context.imports.stage(content=content, filename="nir.csv",
                                  kind=ImportKind.SPECTRA, study_id="E1", user=user)
    assert again.duplicate_of == first.import_batch_id
    preview = context.imports.preview(again.import_batch_id, PLAN, user)
    assert not preview.ok and preview.duplicate_of == first.import_batch_id
    with pytest.raises(DuplicateImportError, match="nada foi duplicado"):
        context.imports.confirm(again.import_batch_id, PLAN, user)
    assert count(context, SpectrumRow) == 6


def test_confirmed_import_cannot_be_confirmed_twice(context, user):
    staged, _ = do_import(context, user, synthetic.wide_csv(DATA), "nir.csv",
                          ImportKind.SPECTRA)
    with pytest.raises(ImportStateError):
        context.imports.confirm(staged.import_batch_id, PLAN, user)


def test_existing_measurements_are_not_silently_duplicated_as_replicates(context, user):
    do_import(context, user, synthetic.wide_csv(DATA), "a.csv", ImportKind.SPECTRA)
    other = synthetic.make_set(3, 2, seed=9)   # mesmas amostras, outro arquivo
    _, report = do_import(context, user, synthetic.wide_csv(other), "b.csv",
                          ImportKind.SPECTRA)
    assert report.rejected == 6 and report.spectra_written == 0
    assert "já existe na base" in report.lines[0].message
    third = synthetic.make_set(3, 2, seed=10)
    declared = PLAN.model_copy(update={"repeated_rows_are_replicates": True})
    _, report = do_import(context, user, synthetic.wide_csv(third), "c.csv",
                          ImportKind.SPECTRA, declared)
    assert (report.alerts, report.spectra_written) == (6, 6)
    assert count(context, SpectrumRow, SpectrumRow.technical_replicate == 2) == 6


def test_divergent_metadata_is_alerted_and_existing_value_kept(context, user):
    do_import(context, user, synthetic.wide_csv(DATA), "a.csv", ImportKind.SPECTRA)
    refs = (b"Amostra;Genotype;Parametro;Valor;Unidade\n"
            b"S001;OUTRO;C18_2;45,0;%\n")
    _, report = do_import(context, user, refs, "r.csv", ImportKind.REFERENCE, ImportPlan())
    assert report.alerts == 1 and "diverge do cadastro" in report.lines[0].message
    with session_scope(context.session_factory) as db:
        sample = db.scalar(select(SampleRow).where(SampleRow.sample_id == "S001"))
        assert sample.genotype == "G01"


def test_identity_conflict_blocks_preview_and_import_until_confirmed(context, user):
    one = synthetic.make_set(1, 1, seed=3)
    one.sample_ids = ["A001"]
    staged = context.imports.stage(content=synthetic.wide_csv(one), filename="a.csv",
                                   kind=ImportKind.SPECTRA, study_id="E1", user=user)
    plan = PLAN.model_copy(update={"user_sample_id": "A002"})
    preview = context.imports.preview(staged.import_batch_id, plan, user)
    assert not preview.ok and "CONFLITO DE IDENTIFICAÇÃO" in preview.blocking_error
    assert preview.conflict.candidates == {"FILE": "A001", "USER_ENTERED": "A002"}
    with pytest.raises(IdentityConflictError):
        context.imports.confirm(staged.import_batch_id, plan, user)
    assert count(context, SampleRow) == 0
    confirmed = plan.model_copy(update={"conflict_confirmed": True})
    context.imports.confirm(staged.import_batch_id, confirmed, user)
    with session_scope(context.session_factory) as db:
        sample = db.scalar(select(SampleRow))
        assert (sample.sample_id, sample.sample_id_origin) == ("A002", "USER_CONFIRMED")


def test_templates_are_saved_listed_and_reusable(context, user):
    plan = ImportPlan(signal_type="absorbance", wavelength_unit="nm", delimiter=";",
                      decimal=",", has_header=True, sample_defaults={"matrix": "farinha"},
                      spectrum_defaults={"instrument": "FT-NIR lab A"})
    saved = context.imports.save_template(
        TemplateIn(name="FT-NIR do laboratório A", kind=ImportKind.SPECTRA, plan=plan), user)
    (listed,) = context.imports.list_templates()
    assert listed == saved and listed.plan == plan
    with pytest.raises(LipidenceError, match="já existe template"):
        context.imports.save_template(
            TemplateIn(name="FT-NIR do laboratório A", kind=ImportKind.SPECTRA, plan=plan), user)
    do_import(context, user, synthetic.wide_csv(DATA), "a.csv", ImportKind.SPECTRA, listed.plan)
    with session_scope(context.session_factory) as db:
        sample = db.scalar(select(SampleRow).limit(1))
        assert sample.matrix == "farinha"
        assert sample.field_origins == {"matrix": "USER_ENTERED", "genotype": "FILE"}
        assert db.scalar(select(SpectrumRow.instrument).limit(1)) == "FT-NIR lab A"


def test_template_with_unknown_role_is_rejected(context, user):
    with pytest.raises(ConfigurationError, match="papel de coluna desconhecido"):
        context.imports.save_template(
            TemplateIn(name="x", kind=ImportKind.SPECTRA,
                       plan=ImportPlan(columns={"a": "inventado"})), user)


def test_manual_registration_of_sample_and_reference(context, user):
    sample_id = context.imports.register_sample(
        ManualSampleIn(study_id="E1", sample_id=" sorgo-l01-045 ",
                       metadata={"genotype": "BRS 330", "notes": "manual"}), user)
    assert sample_id == "SORGO-L01-045"
    with pytest.raises(LipidenceError, match="já existe"):
        context.imports.register_sample(
            ManualSampleIn(study_id="E1", sample_id="SORGO-L01-045"), user)
    with pytest.raises(PlanError, match="metadados desconhecidos"):
        context.imports.register_sample(
            ManualSampleIn(study_id="E1", sample_id="X", metadata={"cor": "azul"}), user)
    ref = ManualReferenceIn(study_id="E1", sample_id="sorgo-l01-045", parameter="tbars",
                            value=0.7, unit="mg MDA/kg")
    assert context.imports.register_reference(ref, user) == 1
    with pytest.raises(PlanError, match="informe a replicata"):
        context.imports.register_reference(ref, user)
    assert context.imports.register_reference(
        ref.model_copy(update={"replicate": 2}), user) == 2
    for bad in ({"parameter": "C99"}, {"unit": "ppm"}):
        with pytest.raises(PlanError):
            context.imports.register_reference(ref.model_copy(update=bad), user)
    with pytest.raises(LipidenceError, match="não existe"):
        context.imports.register_reference(ref.model_copy(update={"sample_id": "ZZ"}), user)
    with session_scope(context.session_factory) as db:
        sample = db.scalar(select(SampleRow))
        assert sample.sample_id_origin == "USER_ENTERED" and sample.extra == {"notes": "manual"}
        assert db.scalar(select(func.count()).select_from(ReferenceAnalysisRow)) == 2


def test_query_filters_by_study_genotype_and_completeness(context, user):
    do_import(context, user, synthetic.wide_csv(DATA, references=True), "c.csv",
              ImportKind.COMBINED)
    extra = synthetic.make_set(1, 2, seed=8)
    extra.sample_ids = ["X1", "X2"]
    do_import(context, user, synthetic.wide_csv(extra), "x.csv", ImportKind.SPECTRA, study="E2")
    base = context.base
    assert base.list_samples(SampleFilters()).total == 8
    assert base.list_samples(SampleFilters(study_id="E2")).total == 2
    assert [s.sample_id for s in base.list_samples(SampleFilters(genotype="G02")).samples] == [
        "S003", "S004"]
    assert base.list_samples(SampleFilters(completeness="complete")).total == 6
    assert base.list_samples(SampleFilters(completeness="no_reference")).total == 2
    assert base.list_samples(SampleFilters(completeness="no_spectrum")).total == 0
    assert base.list_samples(SampleFilters(limit=3, offset=6)).samples[0].sample_id == "X1"
    assert base.summary("E2").samples == 2
    options = base.filter_options()
    assert options.studies == ["E1", "E2"] and options.genotypes == ["G01", "G02", "G03"]
    with pytest.raises(ConfigurationError, match="completude"):
        base.list_samples(SampleFilters(completeness="talvez"))
