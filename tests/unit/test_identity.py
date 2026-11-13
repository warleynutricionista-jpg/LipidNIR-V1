import pytest

from lipidence_modular.core.errors import IdentityConflictError, IdentityError
from lipidence_modular.data.identity.normalization import normalize_sample_id, same_sample
from lipidence_modular.data.identity.resolution import (
    UNKNOWN,
    FieldOrigin,
    resolve_optional,
    resolve_sample_id,
)


def test_normalization_trims_collapses_and_uppercases_keeping_raw():
    ident = normalize_sample_id("  sorgo-l01  045 ")
    assert ident.sample_id == "SORGO-L01 045"
    assert ident.sample_id_raw == "  sorgo-l01  045 "


def test_spreadsheet_integer_float_is_read_as_integer():
    assert normalize_sample_id(17.0).sample_id == "17"


@pytest.mark.parametrize("raw", [None, "", "   ", float("nan"), True, "x" * 129])
def test_inv01_missing_or_invalid_sample_id_is_rejected(raw):
    with pytest.raises(IdentityError):
        normalize_sample_id(raw)


def test_inv01_link_only_by_exact_normalized_identity():
    assert same_sample("a001", " A001 ")
    assert not same_sample("A001", "A002")
    assert not same_sample("A001", "A-001")  # sem correspondência aproximada
    assert not same_sample("A001", "A0001")


def test_file_value_alone_is_accepted_with_file_origin():
    resolved = resolve_sample_id(from_file="a001")
    assert (resolved.value, resolved.origin) == ("A001", FieldOrigin.FILE)


def test_inv01_filename_suggestion_is_never_definitive_identity():
    with pytest.raises(IdentityError, match="confirmação"):
        resolve_sample_id(auto_detected="A001")
    resolved = resolve_sample_id(auto_detected="A001", user_value="a001")
    assert resolved.origin is FieldOrigin.USER_CONFIRMED


def test_user_entered_without_other_source():
    assert resolve_sample_id(user_value="A9").origin is FieldOrigin.USER_ENTERED


def test_inv07_conflict_between_file_and_user_stops_the_flow():
    with pytest.raises(IdentityConflictError) as exc:
        resolve_sample_id(from_file="A001", user_value="A002")
    assert exc.value.candidates == {"FILE": "A001", "USER_ENTERED": "A002"}
    assert "CONFLITO DE IDENTIFICAÇÃO" in str(exc.value)


def test_conflict_resolved_only_by_explicit_confirmation():
    resolved = resolve_sample_id(from_file="A001", user_value="A002", conflict_confirmed=True)
    assert (resolved.value, resolved.origin) == ("A002", FieldOrigin.USER_CONFIRMED)


def test_no_identity_at_all_is_an_error():
    with pytest.raises(IdentityError):
        resolve_sample_id()


def test_optional_missing_field_becomes_unknown_never_invented():
    assert resolve_optional(None, FieldOrigin.FILE).value == UNKNOWN
    assert resolve_optional("  ", FieldOrigin.FILE).value == UNKNOWN
    assert resolve_optional(" FT-NIR ", FieldOrigin.FILE).value == "FT-NIR"
