"""Ponto de partida: backend/tests/unit/test_spectral_quality.py@e027e41."""

import numpy as np
import pytest

from lipidence_modular.data.validators.spectral_quality import (
    default_thresholds,
    is_uniform_grid,
    validate_spectrum,
    validate_wavelength_grid,
)

AXIS = np.arange(1100.0, 2500.0, 5.0)
GOOD = 0.5 + 0.2 * np.sin(AXIS / 150.0)


def codes(issues):
    return {i.code for i in issues}


def test_good_spectrum_is_valid():
    report = validate_spectrum(AXIS, GOOD, is_absorbance=True)
    assert report.is_valid and not report.warnings


@pytest.mark.parametrize(
    ("axis", "code"),
    [
        (AXIS[:50], "wavelength_too_few_points"),
        (np.where(np.arange(AXIS.size) == 5, np.nan, AXIS), "wavelength_non_finite"),
        (AXIS[::-1], "wavelength_not_sorted"),
        (np.concatenate([AXIS[:-1], AXIS[-2:-1]]), "wavelength_duplicates"),
        (AXIS - 1200.0, "wavelength_non_positive"),
        (AXIS + 5000.0, "wavelength_outside_nir"),
    ],
)
def test_invalid_grids_are_errors(axis, code):
    issues = validate_wavelength_grid(axis)
    assert code in codes(i for i in issues if i.severity == "error")


def test_incomplete_spectrum_is_rejected():
    values = GOOD.copy()
    values[10] = np.nan
    report = validate_spectrum(AXIS, values, is_absorbance=True)
    assert not report.is_valid and "intensity_non_finite" in codes(report.errors)
    assert "espectro incompleto" in report.errors[0].message


def test_flat_spectrum_is_rejected_and_length_mismatch_too():
    assert "flat_spectrum" in codes(
        validate_spectrum(AXIS, np.full(AXIS.size, 0.5), is_absorbance=True).errors)
    assert "length_mismatch" in codes(
        validate_spectrum(AXIS, GOOD[:-1], is_absorbance=True).errors)


def test_absorbance_range_checked_only_for_absorbance():
    values = GOOD * 60.0  # reflectância em %
    assert "intensity_out_of_range" in codes(
        validate_spectrum(AXIS, values, is_absorbance=True).warnings)
    assert "intensity_out_of_range" not in codes(
        validate_spectrum(AXIS, values, is_absorbance=False).warnings)


def test_noisy_spectrum_gets_low_snr_warning():
    noisy = GOOD + np.random.default_rng(0).normal(0, 0.05, AXIS.size)
    report = validate_spectrum(AXIS, noisy, is_absorbance=True)
    assert report.is_valid and "low_snr" in codes(report.warnings)


def test_uniform_grid_detection_and_thresholds_are_configurable():
    assert is_uniform_grid(AXIS)
    assert not is_uniform_grid(np.concatenate([AXIS[:100], AXIS[100:] + 3.0]))
    strict = {**default_thresholds(), "min_points": 1000}
    assert "wavelength_too_few_points" in codes(validate_wavelength_grid(AXIS, strict))
