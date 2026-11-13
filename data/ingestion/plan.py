"""Plano de importação: tudo o que o usuário confirma antes de importar (seção 8.7)."""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field

from lipidence_modular.data.schemas.spectral import AxisUnit, SignalType


class ImportKind(enum.StrEnum):
    SPECTRA = "spectra"
    REFERENCE = "reference"
    COMBINED = "combined"


class SignalScale(enum.StrEnum):
    FRACTION = "fraction"
    PERCENT = "percent"


class ImportPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Leitura do arquivo (None = usar o detectado)
    delimiter: str | None = None
    decimal: str | None = None
    has_header: bool | None = None
    sheet: str | None = None
    # Mapeamento de colunas: nome da coluna -> papel (None = usar o sugerido)
    columns: dict[str, str] | None = None
    # Espectros: declarações obrigatórias, nunca adivinhadas
    signal_type: SignalType | None = None
    wavelength_unit: AxisUnit | None = None
    convert_to_absorbance: bool = False
    signal_scale: SignalScale | None = None
    # Identidade
    user_sample_id: str | None = None
    conflict_confirmed: bool = False
    repeated_rows_are_replicates: bool = False
    # Referências
    reference_units: dict[str, str] = Field(default_factory=dict)
    parameter_map: dict[str, str] = Field(default_factory=dict)
    unit_map: dict[str, str] = Field(default_factory=dict)
    reference_defaults: dict[str, str] = Field(default_factory=dict)
    # Metadados informados pelo usuário para todos os itens do arquivo
    sample_defaults: dict[str, str] = Field(default_factory=dict)
    spectrum_defaults: dict[str, str] = Field(default_factory=dict)
