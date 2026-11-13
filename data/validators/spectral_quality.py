"""Validação da grade espectral e do espectro.

# Portado de backend/app/ml/spectral_quality.py@e027e41 (validate_wavelength_grid,
# validate_spectrum, _estimate_snr). Adaptações: limiares lidos de
# config/spectral_quality.yaml (todos PROVISORIO); mensagens em português; a faixa de
# absorbância só é conferida para sinal de absorbância; ``fatty_acid_sum_check`` não foi
# portado (ver REUSE_MAP.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import yaml

from lipidence_modular.config import CONFIG_DIR

QUALITY_FILE = CONFIG_DIR / "spectral_quality.yaml"
ERROR, WARNING, INFO = "error", "warning", "info"


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str
    message: str


@dataclass
class QualityReport:
    issues: list[QualityIssue] = field(default_factory=list)
    snr: float | None = None
    dynamic_range: float | None = None
    saturation_ratio: float = 0.0

    def add(self, code: str, severity: str, message: str) -> None:
        self.issues.append(QualityIssue(code, severity, message))

    @property
    def errors(self) -> list[QualityIssue]:
        return [i for i in self.issues if i.severity == ERROR]

    @property
    def warnings(self) -> list[QualityIssue]:
        return [i for i in self.issues if i.severity == WARNING]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@lru_cache(maxsize=1)
def default_thresholds() -> dict:
    data = yaml.safe_load(QUALITY_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k != "status"}


def estimate_snr(values: np.ndarray) -> float:
    """Estimativa DER-SNR: mediana do sinal sobre o ruído das segundas diferenças."""
    if values.size < 5:
        return float("inf")
    signal = float(np.median(np.abs(values)))
    noise_samples = np.abs(2.0 * values[2:-2] - values[:-4] - values[4:])
    noise = 1.482602 / np.sqrt(6.0) * float(np.median(noise_samples))
    if noise < 1e-12:
        return float("inf")
    return signal / noise


def validate_wavelength_grid(axis_nm, thresholds: dict | None = None) -> list[QualityIssue]:
    """Grade em nm: finita, positiva, estritamente crescente (logo, sem duplicatas)."""
    cfg = thresholds or default_thresholds()
    axis = np.asarray(axis_nm, dtype=float)
    issues: list[QualityIssue] = []
    if axis.size < cfg["min_points"]:
        return [QualityIssue(
            "wavelength_too_few_points", ERROR,
            f"espectro com {axis.size} pontos; o mínimo é {cfg['min_points']}",
        )]
    if axis.size > cfg["max_points"]:
        issues.append(QualityIssue(
            "wavelength_too_many_points", WARNING,
            f"espectro com {axis.size} pontos (acima de {cfg['max_points']})",
        ))
    if np.any(~np.isfinite(axis)):
        issues.append(QualityIssue(
            "wavelength_non_finite", ERROR, "eixo espectral com valor não numérico"
        ))
        return issues
    if np.any(axis <= 0):
        issues.append(QualityIssue(
            "wavelength_non_positive", ERROR, "comprimentos de onda devem ser positivos"
        ))
    diffs = np.diff(axis)
    if np.unique(axis).size != axis.size:
        issues.append(QualityIssue(
            "wavelength_duplicates", ERROR, "comprimentos de onda duplicados no eixo"
        ))
    elif np.any(diffs <= 0):
        issues.append(QualityIssue(
            "wavelength_not_sorted", ERROR, "eixo espectral não é estritamente crescente"
        ))
    low, high = float(axis.min()), float(axis.max())
    if low < cfg["nir_min_nm"] or high > cfg["nir_max_nm"]:
        all_outside = high < cfg["nir_min_nm"] or low > cfg["nir_max_nm"]
        issues.append(QualityIssue(
            "wavelength_outside_nir" if all_outside else "wavelength_partially_outside_nir",
            ERROR if all_outside else WARNING,
            f"eixo de {low:.1f} a {high:.1f} nm; faixa NIR esperada: "
            f"{cfg['nir_min_nm']} a {cfg['nir_max_nm']} nm",
        ))
    if diffs.size and np.all(diffs > 0):
        mean_step = float(np.mean(diffs))
        if float(np.std(diffs)) / mean_step > cfg["irregular_step_cv"]:
            issues.append(QualityIssue(
                "wavelength_irregular_sampling", INFO,
                "grade com espaçamento irregular; derivadas exigem grade uniforme",
            ))
    return issues


def is_uniform_grid(axis_nm, rtol: float = 1e-3) -> bool:
    diffs = np.diff(np.asarray(axis_nm, dtype=float))
    return bool(diffs.size and np.all(diffs > 0) and np.ptp(diffs) <= rtol * np.mean(diffs))


def validate_spectrum(axis_nm, values, *, is_absorbance: bool,
                      thresholds: dict | None = None) -> QualityReport:
    cfg = thresholds or default_thresholds()
    axis = np.asarray(axis_nm, dtype=float)
    y = np.asarray(values, dtype=float)
    report = QualityReport(issues=list(validate_wavelength_grid(axis, cfg)))
    if axis.size != y.size:
        report.add("length_mismatch", ERROR,
                   f"eixo ({axis.size}) e sinal ({y.size}) com tamanhos diferentes")
        return report
    non_finite = int(np.sum(~np.isfinite(y)))
    if non_finite:
        report.add("intensity_non_finite", ERROR,
                   f"espectro incompleto: {non_finite} valor(es) ausente(s) ou não numérico(s)")
        return report
    if y.size == 0:
        return report
    if is_absorbance:
        out = int(np.sum((y < cfg["absorbance_min"]) | (y > cfg["absorbance_max"])))
        if out:
            report.add(
                "intensity_out_of_range", WARNING,
                f"{out} valor(es) fora de [{cfg['absorbance_min']}, {cfg['absorbance_max']}]; "
                "conferir o tipo de sinal declarado",
            )
    y_min, y_max = float(y.min()), float(y.max())
    pinned = max(int(np.sum(y - y_min < 1e-9)) - 1, 0) + max(int(np.sum(y_max - y < 1e-9)) - 1, 0)
    report.saturation_ratio = pinned / y.size
    report.dynamic_range = y_max - y_min
    if report.dynamic_range < cfg["min_dynamic_range"]:
        report.add("flat_spectrum", ERROR,
                   f"espectro praticamente plano (amplitude {report.dynamic_range:.2e})")
        return report
    if report.saturation_ratio > cfg["max_saturation_ratio"]:
        report.add("detector_saturation", WARNING,
                   f"{report.saturation_ratio:.1%} dos pontos presos nos extremos (saturação?)")
    snr = estimate_snr(y)
    report.snr = snr if np.isfinite(snr) else None
    if np.isfinite(snr) and snr < cfg["min_snr"]:
        report.add("low_snr", WARNING,
                   f"relação sinal-ruído estimada ({snr:.1f}) abaixo de {cfg['min_snr']}")
    return report
