"""Caminho único de ingestão: layouts, identidade, sinal, eixo, duplicatas, referências."""

import numpy as np
import pytest

from lipidence_modular.core.errors import IdentityConflictError
from lipidence_modular.data.identity.resolution import FieldOrigin
from lipidence_modular.data.importers.table import read_table
from lipidence_modular.data.ingestion.plan import ImportPlan
from lipidence_modular.data.ingestion.reference import parse_reference
from lipidence_modular.data.ingestion.spectra import PlanError, detect_layout, parse_spectra
from lipidence_modular.data.mapping import roles
from lipidence_modular.data.reference.vocabulary import default_vocabulary
from lipidence_modular.data.schemas.issues import IssueLog
from lipidence_modular.tests.fixtures import synthetic

VOCAB = default_vocabulary()
DATA = synthetic.make_set(3, 2, seed=1)
PLAN = ImportPlan(signal_type="absorbance", wavelength_unit="nm")


def run_spectra(content, name="f.csv", plan=PLAN, columns=None):
    table = read_table(content, name)
    mapping = columns or roles.suggest_mapping(
        table.columns, table.detection.decimal, VOCAB, table.detection.has_header)
    log = IssueLog()
    return parse_spectra(table, mapping, plan, name, log), log


def run_reference(content, plan=None, name="r.csv"):
    table = read_table(content, name)
    mapping = roles.suggest_mapping(table.columns, table.detection.decimal, VOCAB, True)
    log = IssueLog()
    return parse_reference(table, mapping, plan or ImportPlan(), VOCAB, log), log


def test_wide_layout_parses_all_samples_with_metadata_origin():
    spectra, log = run_spectra(synthetic.wide_csv(DATA))
    assert [s.sample_id for s in spectra] == DATA.sample_ids
    assert np.allclose(spectra[0].axis_nm, DATA.axis_nm)
    assert np.allclose(spectra[2].values, DATA.spectra[2], atol=1e-6)
    assert spectra[0].sample_metadata == {"genotype": "G01"}
    assert spectra[0].metadata_origins == {"genotype": "FILE"}
    assert log.counts() == {"received": 6, "imported": 6, "alerts": 0, "rejected": 0}


def test_inv02_three_layouts_and_xlsx_give_the_same_vector():
    wide, _ = run_spectra(synthetic.wide_csv(DATA))
    long, _ = run_spectra(synthetic.long_csv(DATA))
    xlsx, _ = run_spectra(synthetic.wide_xlsx(DATA), "f.xlsx")
    single, _ = run_spectra(
        synthetic.single_txt(DATA, 0), "S001.txt",
        ImportPlan(signal_type="absorbance", wavelength_unit="nm", user_sample_id="S001"))
    assert [s.sample_id for s in long] == DATA.sample_ids
    for other in (long[0], xlsx[0], single[0]):
        assert other.sample_id == "S001"
        assert np.array_equal(other.axis_nm, wide[0].axis_nm)
        assert np.allclose(other.values, wide[0].values, atol=1e-6)


def test_inv07_signal_type_and_axis_unit_are_never_guessed():
    for plan in (ImportPlan(wavelength_unit="nm"), ImportPlan(signal_type="absorbance")):
        with pytest.raises(PlanError, match="declaração obrigatória"):
            run_spectra(synthetic.wide_csv(DATA), plan=plan)


def test_inv01_single_file_name_is_only_a_suggestion():
    spectra, log = run_spectra(synthetic.single_txt(DATA, 0), "S001.txt")
    assert spectra == [] and log.counts()["rejected"] == 1
    assert "confirmação" in log.issues[0].message
    spectra, _ = run_spectra(
        synthetic.single_txt(DATA, 0), "S001.txt",
        ImportPlan(signal_type="absorbance", wavelength_unit="nm", user_sample_id="s001"))
    assert spectra[0].sample_id_origin is FieldOrigin.USER_CONFIRMED
    spectra, _ = run_spectra(
        synthetic.single_txt(DATA, 0), "leitura_17.txt",
        ImportPlan(signal_type="absorbance", wavelength_unit="nm", user_sample_id="A9"))
    assert (spectra[0].sample_id, spectra[0].sample_id_origin) == ("A9", FieldOrigin.USER_ENTERED)


def test_inv07_file_id_versus_user_id_conflict_requires_confirmation():
    one = synthetic.make_set(1, 1, seed=3)
    one.sample_ids = ["A001"]
    plan = ImportPlan(signal_type="absorbance", wavelength_unit="nm", user_sample_id="A002")
    with pytest.raises(IdentityConflictError) as exc:
        run_spectra(synthetic.wide_csv(one), plan=plan)
    assert exc.value.candidates == {"FILE": "A001", "USER_ENTERED": "A002"}
    spectra, _ = run_spectra(
        synthetic.wide_csv(one), plan=plan.model_copy(update={"conflict_confirmed": True}))
    assert spectra[0].sample_id == "A002"
    assert spectra[0].sample_id_origin is FieldOrigin.USER_CONFIRMED
    assert "substituído por confirmação" in spectra[0].provenance[-1]


def test_user_sample_id_with_many_samples_is_a_plan_error():
    plan = ImportPlan(signal_type="absorbance", wavelength_unit="nm", user_sample_id="X")
    with pytest.raises(PlanError, match="única amostra"):
        run_spectra(synthetic.wide_csv(DATA), plan=plan)


def test_missing_sample_id_and_bad_values_are_rejected_per_item():
    text = synthetic.wide_csv(DATA).decode().splitlines()
    cells = text[1].split(";")
    cells[0] = ""
    text[1] = ";".join(cells)                      # sem sample_id
    cells = text[2].split(";")
    cells[10] = "erro"
    text[2] = ";".join(cells)                      # valor não numérico
    cells = text[3].split(";")
    cells[20] = ""
    text[3] = ";".join(cells)                      # espectro incompleto
    spectra, log = run_spectra("\n".join(text).encode())
    assert [s.sample_id for s in spectra] == DATA.sample_ids[3:]
    assert log.counts() == {"received": 6, "imported": 3, "alerts": 0, "rejected": 3}
    assert {i.code for i in log.issues} == {
        "sample_id_missing", "non_numeric", "intensity_non_finite"}


def test_duplicate_sample_id_is_rejected_unless_declared_as_replicates():
    dup = synthetic.make_set(2, 2, seed=2)
    dup.sample_ids = ["A017", "A017", "A018", "A019"]
    spectra, log = run_spectra(synthetic.wide_csv(dup))
    assert [s.sample_id for s in spectra] == ["A018", "A019"]
    assert log.counts()["rejected"] == 2
    assert all("A017: sample_id duplicado" in i.message for i in log.issues)
    plan = PLAN.model_copy(update={"repeated_rows_are_replicates": True})
    spectra, log = run_spectra(synthetic.wide_csv(dup), plan=plan)
    assert [(s.sample_id, s.technical_replicate) for s in spectra[:2]] == [
        ("A017", 1), ("A017", 2)]
    assert log.counts()["rejected"] == 0


def test_axis_in_wavenumber_is_converted_explicitly_and_sorted():
    axis_cm = 1.0e7 / DATA.axis_nm
    table = "cm1\tabs\n" + "\n".join(
        f"{w:.6f}\t{v:.6f}" for w, v in zip(axis_cm, DATA.spectra[0], strict=True))
    plan = ImportPlan(signal_type="absorbance", wavelength_unit="cm-1", user_sample_id="A1")
    spectra, _ = run_spectra(table.encode(), "x.txt", plan)
    assert np.allclose(spectra[0].axis_nm, DATA.axis_nm, atol=1e-3)
    assert np.all(np.diff(spectra[0].axis_nm) > 0)
    assert any("cm-1 para nm" in note for note in spectra[0].provenance)


def test_reflectance_is_converted_only_when_declared_and_recorded():
    refl = synthetic.make_set(1, 2, seed=4)
    refl.spectra = 10.0 ** (-refl.spectra)  # R = 10^-A
    content = synthetic.wide_csv(refl)
    kept, _ = run_spectra(content, plan=ImportPlan(
        signal_type="reflectance", wavelength_unit="nm"))
    assert kept[0].signal_type == "reflectance" and kept[0].provenance == []
    converted, _ = run_spectra(content, plan=ImportPlan(
        signal_type="reflectance", wavelength_unit="nm", convert_to_absorbance=True,
        signal_scale="fraction"))
    assert converted[0].signal_type == "absorbance"
    assert np.allclose(converted[0].values, -np.log10(kept[0].values), atol=1e-6)
    assert "log10(1/R)" in converted[0].provenance[0]
    with pytest.raises(PlanError, match="signal_scale"):
        run_spectra(content, plan=ImportPlan(
            signal_type="reflectance", wavelength_unit="nm", convert_to_absorbance=True))


def test_layout_detection_from_mapping():
    assert detect_layout({"a": "sample_id", "b": "spectral"}) == "wide"
    assert detect_layout({"a": "sample_id", "b": "wavelength", "c": "signal"}) == "long"
    assert detect_layout({"b": "wavelength", "c": "signal"}) == "single"
    for bad in ({"b": "spectral"}, {"a": "sample_id"},
                {"a": "spectral", "b": "wavelength", "c": "signal", "d": "sample_id"}):
        with pytest.raises(PlanError):
            detect_layout(bad)


def test_reference_long_format_with_vocabulary():
    refs, log = run_reference(synthetic.reference_long_csv(DATA))
    assert len(refs) == 12 and log.counts()["imported"] == 12
    first = refs[0]
    assert (first.sample_id, first.parameter, first.unit, first.method) == (
        "S001", "C18:2", "%", "GC-FID")
    assert first.value == pytest.approx(DATA.targets["C18:2"][0], abs=1e-3)
    assert first.analysis_type == "fatty_acid_profile"


def test_reference_rejections_match_section_8_7_validations():
    content = (
        b"Amostra;Parametro;Valor;Unidade\n"
        b"A001;C18_2;45,1;%\n"
        b"A122;TBARS;0,8;\n"            # referência sem unidade
        b"A123;C18_2;abc;%\n"           # valor não numérico
        b"A124;C20_5;1,0;%\n"           # parâmetro fora do vocabulário
        b"A125;TBARS;0,5;ppm\n"         # unidade desconhecida
        b";C18_2;40,0;%\n"              # sem sample_id
        b"A126;C18_2;140,0;%\n"         # fora da faixa plausível: alerta, importa
    )
    refs, log = run_reference(content)
    assert [r.sample_id for r in refs] == ["A001", "A126"]
    assert log.counts() == {"received": 7, "imported": 1, "alerts": 1, "rejected": 5}
    messages = " | ".join(i.message for i in log.issues)
    for expected in ("referência sem unidade", "valor não numérico", "fora do vocabulário",
                     "unidade desconhecida", "sample_id ausente", "faixa plausível"):
        assert expected in messages


def test_inv07_unknown_parameter_or_unit_needs_confirmed_mapping():
    content = b"Amostra;Parametro;Valor;Unidade\nA1;Linoleic acid total;45,1;pct\n"
    assert run_reference(content)[0] == []
    plan = ImportPlan(parameter_map={"Linoleic acid total": "C18:2"}, unit_map={"pct": "%"})
    refs, _ = run_reference(content, plan)
    assert (refs[0].parameter, refs[0].unit) == ("C18:2", "%")


def test_wide_reference_needs_unit_from_header_or_plan():
    content = b"Sample;C18_2;TBARS (mg MDA/kg)\nA1;45.1;0.8\n"
    refs, log = run_reference(content)
    assert refs == [] and "C18:2: referência sem unidade" in log.issues[0].message
    refs, log = run_reference(content, ImportPlan(reference_units={"C18:2": "%"}))
    assert {(r.parameter, r.unit) for r in refs} == {("C18:2", "%"), ("TBARS", "mg MDA/kg")}


def test_duplicate_measurement_needs_replicate_declaration():
    content = b"Amostra;Parametro;Valor;Unidade\nA1;C18_2;45.0;%\nA1;C18_2;45.4;%\n"
    refs, log = run_reference(content)
    assert refs == [] and log.counts()["rejected"] == 2
    refs, _ = run_reference(content, ImportPlan(repeated_rows_are_replicates=True))
    assert [r.replicate for r in refs] == [1, 2]
    with_column = (b"Amostra;Parametro;Valor;Unidade;Replicata\n"
                   b"A1;C18_2;45.0;%;1\nA1;C18_2;45.4;%;2\n")
    refs, _ = run_reference(with_column)
    assert [r.replicate for r in refs] == [1, 2]
