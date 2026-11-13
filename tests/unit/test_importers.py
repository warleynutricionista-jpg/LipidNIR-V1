import pytest

from lipidence_modular.data.importers.table import ImportFileError, read_table, to_float
from lipidence_modular.data.mapping import roles
from lipidence_modular.data.reference.vocabulary import default_vocabulary, fold
from lipidence_modular.tests.fixtures import synthetic

VOCAB = default_vocabulary()


def test_brazilian_csv_semicolon_and_decimal_comma_are_detected():
    table = read_table(b"Sample;1000;1010\nA1;0,512;0,498\nA2;0,601;0,577\n", "x.csv")
    d = table.detection
    assert (d.delimiter, d.decimal, d.has_header) == (";", ",", True)
    assert to_float(table.rows[0][1], d.decimal) == pytest.approx(0.512)


def test_comma_delimited_uses_dot_decimal():
    table = read_table(b"sample_id,wavelength,signal\nA1,1000,0.5\nA1,1010,0.6\n", "x.csv")
    assert (table.detection.delimiter, table.detection.decimal) == (",", ".")


def test_tab_file_without_header_gets_generic_column_names():
    table = read_table(synthetic.single_txt(synthetic.make_set(1, 1)), "a.txt")
    assert table.detection.delimiter == "\t" and table.detection.has_header is False
    assert table.columns == ["col1", "col2"]


def test_whitespace_separated_txt():
    table = read_table(b"1000   0.51\n1010   0.52\n1020   0.53\n", "a.txt")
    assert table.detection.delimiter == "whitespace" and len(table.rows) == 3


def test_overrides_replace_detection():
    table = read_table(b"a|b\n1,5|2,5\n", "x.txt", delimiter="|", decimal=",")
    assert to_float(table.rows[0][0], ",") == 1.5


def test_xlsx_is_read_with_numeric_headers_as_text():
    table = read_table(synthetic.wide_xlsx(synthetic.make_set(2, 2)), "x.xlsx")
    assert table.detection.file_format == "xlsx" and table.detection.sheet == "espectros"
    assert table.columns[:3] == ["Sample", "Genotype", "1100"]
    assert isinstance(table.rows[0][2], float)


@pytest.mark.parametrize(
    ("content", "name"),
    [(b"", "x.csv"), (b"a;b\n", "x.csv"), (b"x", "x.jdx"), (b"x", "semextensao"),
     (b"nao e planilha", "x.xlsx")],
)
def test_inv07_unreadable_or_unsupported_files_are_explicit_errors(content, name):
    with pytest.raises(ImportFileError):
        read_table(content, name)


def test_incompatible_overrides_are_rejected():
    with pytest.raises(ImportFileError):
        read_table(b"a,b\n1,2\n", "x.csv", delimiter=",", decimal=",")
    with pytest.raises(ImportFileError):
        read_table(b"a,b\n1,2\n", "x.csv", delimiter="#")


@pytest.mark.parametrize(
    ("cell", "decimal", "expected"),
    [("0,5", ",", 0.5), ("0.5", ".", 0.5), ("1e-3", ".", 0.001), (3, ".", 3.0),
     ("0,5", ".", None), ("0.5", ",", None), ("abc", ".", None), ("", ".", None),
     (None, ".", None), (True, ".", None), ("1.234,5", ",", None), (float("nan"), ".", None)],
)
def test_to_float_never_guesses(cell, decimal, expected):
    assert to_float(cell, decimal) == expected


def test_mapping_suggestion_follows_section_8_7_examples():
    columns = ["Sample", "Batch", "Genotype", "Wavelength", "Abs", "C18_2", "TBARS", "Qualquer"]
    assert roles.suggest_mapping(columns, ".", VOCAB, True) == {
        "Sample": "sample_id", "Batch": "meta:batch", "Genotype": "meta:genotype",
        "Wavelength": "wavelength", "Abs": "signal", "C18_2": "reference:C18:2",
        "TBARS": "reference:TBARS", "Qualquer": "ignore",
    }


def test_numeric_headers_are_spectral_respecting_decimal():
    mapping = roles.suggest_mapping(["Amostra", "1100,5", "1101,0"], ",", VOCAB, True)
    assert list(mapping.values()) == ["sample_id", "spectral", "spectral"]


def test_unit_is_read_from_header():
    assert roles.split_header_unit("TBARS (mg MDA/kg)") == ("TBARS", "mg MDA/kg")
    assert roles.split_header_unit("C18_2 [%]") == ("C18_2", "%")
    assert roles.split_header_unit("C18_2") == ("C18_2", None)


def test_second_candidate_for_same_role_is_left_to_the_user():
    mapping = roles.suggest_mapping(["Sample", "Amostra", "1000"], ".", VOCAB, True)
    assert mapping == {"Sample": "sample_id", "Amostra": "ignore", "1000": "spectral"}


def test_vocabulary_aliases_units_and_range():
    spec = VOCAB.resolve_parameter("c18_2")
    assert spec.name == "C18:2" and VOCAB.resolve_parameter("Linoleico").name == "C18:2"
    assert VOCAB.resolve_parameter("C20:5") is None
    assert VOCAB.resolve_unit(spec, "%") == "%" and VOCAB.resolve_unit(spec, "g/kg") is None
    pv = VOCAB.resolve_parameter("Índice de Peróxidos")
    assert pv.name == "PV" and VOCAB.resolve_unit(pv, "meq O₂/kg") == "meq O2/kg"
    assert spec.in_plausible_range(55.0) and not spec.in_plausible_range(120.0)
    assert VOCAB.status == "PROVISORIO"
    assert fold("Índice de Peróxidos") == "indicedeperoxidos"
