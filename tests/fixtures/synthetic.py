"""Gerador de dados SINTÉTICOS para testes e demonstração (protocolo, regra 7).

# Portado de test_data/generate_nir_datasets.py@e027e41 (generate_realistic_nir_spectrum):
# a ideia de linha de base + bandas gaussianas + ruído. Reescrito para ser determinístico
# por seed, com bandas em posições declaradas (necessário aos controles do ICQ, seção 13.6)
# e estrutura de grupos (genótipos) para os testes de partição.

Nada aqui representa dado experimental: todo dataset derivado leva ``origin: SYNTHETIC``.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np

ORIGIN = "SYNTHETIC"


@dataclass
class SyntheticSet:
    axis_nm: np.ndarray
    spectra: np.ndarray  # (n_amostras, n_pontos), absorbância
    sample_ids: list[str]
    genotypes: list[str]
    targets: dict[str, np.ndarray]


def gaussian(axis: np.ndarray, center: float, width: float) -> np.ndarray:
    return np.exp(-0.5 * ((axis - center) / width) ** 2)


def make_set(n_genotypes: int = 6, per_genotype: int = 4, seed: int = 0,
             axis_nm: np.ndarray | None = None, noise: float = 2e-4) -> SyntheticSet:
    """Espectros com uma banda em 1720 nm modulada por C18:2 e uma em 1930 nm (água)
    independente; TBARS modula uma banda em 2250 nm. Efeito de genótipo no nível de C18:2."""
    rng = np.random.default_rng(seed)
    axis = np.arange(1100.0, 2500.0, 5.0) if axis_nm is None else np.asarray(axis_nm, float)
    n = n_genotypes * per_genotype
    genotype_level = rng.normal(45.0, 6.0, n_genotypes)
    genotypes, c182 = [], []
    for g in range(n_genotypes):
        for _ in range(per_genotype):
            genotypes.append(f"G{g + 1:02d}")
            c182.append(genotype_level[g] + rng.normal(0.0, 1.5))
    c182 = np.clip(np.array(c182), 5.0, 90.0)
    tbars = np.abs(rng.normal(0.8, 0.3, n))
    water = rng.normal(1.0, 0.15, n)
    baseline = 0.4 + 0.00008 * (axis - axis[0])
    spectra = (
        baseline[None, :]
        + rng.normal(0.0, 0.01, (n, 1))  # deslocamento de linha de base por amostra
        + (c182[:, None] / 100.0) * 0.5 * gaussian(axis, 1720.0, 25.0)[None, :]
        + water[:, None] * 0.3 * gaussian(axis, 1930.0, 30.0)[None, :]
        + tbars[:, None] * 0.1 * gaussian(axis, 2250.0, 20.0)[None, :]
        + rng.normal(0.0, noise, (n, axis.size))
    )
    return SyntheticSet(
        axis_nm=axis, spectra=spectra, sample_ids=[f"S{i + 1:03d}" for i in range(n)],
        genotypes=genotypes, targets={"C18:2": c182, "TBARS": tbars},
    )


def fmt(value: float, decimal: str = ".", digits: int = 6) -> str:
    return f"{value:.{digits}f}".replace(".", decimal)


def axis_label(value: float, decimal: str = ".") -> str:
    text = str(int(value)) if float(value).is_integer() else str(value)
    return text.replace(".", decimal)


def wide_csv(data: SyntheticSet, *, delimiter: str = ";", decimal: str = ",",
             with_genotype: bool = True, references: bool = False,
             id_header: str = "Sample") -> bytes:
    """Layout largo. Com ``references=True`` vira o arquivo combinado."""
    header = [id_header] + (["Genotype"] if with_genotype else [])
    header += [axis_label(w, decimal) for w in data.axis_nm]
    if references:
        header += ["C18_2 (%)", "TBARS (mg MDA/kg)"]
    lines = [delimiter.join(header)]
    for i, sample_id in enumerate(data.sample_ids):
        row = [sample_id] + ([data.genotypes[i]] if with_genotype else [])
        row += [fmt(v, decimal) for v in data.spectra[i]]
        if references:
            row += [fmt(data.targets["C18:2"][i], decimal, 3),
                    fmt(data.targets["TBARS"][i], decimal, 3)]
        lines.append(delimiter.join(row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def long_csv(data: SyntheticSet, *, delimiter: str = ",", decimal: str = ".") -> bytes:
    lines = [delimiter.join(["sample_id", "wavelength", "signal"])]
    for i, sample_id in enumerate(data.sample_ids):
        for w, v in zip(data.axis_nm, data.spectra[i], strict=True):
            lines.append(delimiter.join([sample_id, axis_label(w, decimal), fmt(v, decimal)]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def single_txt(data: SyntheticSet, index: int = 0, *, decimal: str = ".") -> bytes:
    """Um arquivo por amostra: duas colunas separadas por tabulação, sem cabeçalho."""
    lines = [f"{axis_label(w, decimal)}\t{fmt(v, decimal)}"
             for w, v in zip(data.axis_nm, data.spectra[index], strict=True)]
    return ("\n".join(lines) + "\n").encode("utf-8")


def reference_long_csv(data: SyntheticSet, *, delimiter: str = ";", decimal: str = ",",
                       sample_ids: list[str] | None = None) -> bytes:
    ids = sample_ids or data.sample_ids
    lines = [delimiter.join(["Amostra", "Parametro", "Valor", "Unidade", "Metodo"])]
    for i, sample_id in enumerate(ids):
        lines.append(delimiter.join(
            [sample_id, "C18_2", fmt(data.targets["C18:2"][i], decimal, 3), "%", "GC-FID"]))
        lines.append(delimiter.join(
            [sample_id, "TBARS", fmt(data.targets["TBARS"][i], decimal, 3), "mg MDA/kg",
             "espectrofotometria"]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def wide_xlsx(data: SyntheticSet) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "espectros"
    sheet.append(["Sample", "Genotype", *[float(w) for w in data.axis_nm]])
    for i, sample_id in enumerate(data.sample_ids):
        sheet.append([sample_id, data.genotypes[i], *[float(v) for v in data.spectra[i]]])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
