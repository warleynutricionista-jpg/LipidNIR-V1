from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field

import numpy as np

from lipidence_modular.data.identity.resolution import FieldOrigin


class SignalType(enum.StrEnum):
    ABSORBANCE = "absorbance"
    REFLECTANCE = "reflectance"
    TRANSMITTANCE = "transmittance"


class AxisUnit(enum.StrEnum):
    NM = "nm"
    CM1 = "cm-1"


CANONICAL_AXIS_UNIT = AxisUnit.NM
AXIS_DECIMALS = 6


def axis_hash(axis_nm: np.ndarray) -> str:
    """Hash estável do eixo espectral (nm, arredondado a ``AXIS_DECIMALS`` casas)."""
    rounded = np.round(np.asarray(axis_nm, dtype=np.float64), AXIS_DECIMALS)
    return hashlib.sha256(rounded.astype("<f8").tobytes()).hexdigest()


# Metadados de amostra com coluna própria; os demais vão para o campo extensível.
SAMPLE_COLUMN_FIELDS = (
    "genotype", "cultivar", "batch", "lot", "matrix", "storage_time", "storage_condition",
)
SAMPLE_EXTRA_FIELDS = (
    "sample_name", "external_sample_id", "processing", "treatment", "biological_replicate",
    "timepoint", "collection_date", "analysis_date", "notes",
)
SAMPLE_FIELDS = SAMPLE_COLUMN_FIELDS + SAMPLE_EXTRA_FIELDS
SPECTRUM_FIELDS = (
    "instrument", "manufacturer", "model", "serial_number", "acquisition_date", "operator",
    "resolution", "number_of_scans", "temperature", "accessory",
)


@dataclass
class ParsedSpectrum:
    item: str
    sample_id: str
    sample_id_raw: str
    sample_id_origin: FieldOrigin
    technical_replicate: int | None
    axis_nm: np.ndarray
    values: np.ndarray
    signal_type: SignalType
    sample_metadata: dict[str, str] = field(default_factory=dict)
    spectrum_metadata: dict[str, str] = field(default_factory=dict)
    provenance: list[str] = field(default_factory=list)
    metadata_origins: dict[str, str] = field(default_factory=dict)
