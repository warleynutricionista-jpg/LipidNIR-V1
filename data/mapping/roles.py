"""Papéis de coluna e sugestão automática de mapeamento.

O mapeamento sugerido é sempre mostrado no preview para confirmação; coluna sem papel
reconhecido fica como ``ignore`` e aparece listada, nunca descartada em silêncio.
"""

from __future__ import annotations

import re

from lipidence_modular.core.errors import ConfigurationError
from lipidence_modular.data.importers.table import to_float
from lipidence_modular.data.reference.vocabulary import Vocabulary, fold
from lipidence_modular.data.schemas.spectral import SAMPLE_FIELDS, SPECTRUM_FIELDS

SAMPLE_ID = "sample_id"
IGNORE = "ignore"
WAVELENGTH = "wavelength"
SIGNAL = "signal"
SPECTRAL = "spectral"
TECHNICAL_REPLICATE = "technical_replicate"
PARAMETER = "parameter"
VALUE = "value"
UNIT = "unit"
REFERENCE_FIELDS = ("method", "replicate", "date", "laboratory", "analysis_type")
SIMPLE_ROLES = (
    SAMPLE_ID, IGNORE, WAVELENGTH, SIGNAL, SPECTRAL, TECHNICAL_REPLICATE, PARAMETER, VALUE,
    UNIT, *REFERENCE_FIELDS,
)
META_PREFIX, SPECTRUM_PREFIX, REFERENCE_PREFIX = "meta:", "spectrum:", "reference:"

_ALIASES = {
    SAMPLE_ID: ["sample", "sampleid", "sample_id", "amostra", "idamostra", "id_amostra",
                "codigo", "codigoamostra", "id"],
    WAVELENGTH: ["wavelength", "wavelengthnm", "nm", "comprimentodeonda", "lambda",
                 "wavenumber", "numerodeonda", "cm1"],
    SIGNAL: ["abs", "absorbance", "absorbancia", "signal", "sinal", "intensity",
             "intensidade", "reflectance", "reflectancia", "transmittance", "transmitancia"],
    TECHNICAL_REPLICATE: ["technicalreplicate", "replicatatecnica", "scan", "leitura"],
    PARAMETER: ["parameter", "parametro", "analyte", "analito"],
    VALUE: ["value", "valor", "result", "resultado"],
    UNIT: ["unit", "unidade", "units"],
    "method": ["method", "metodo"],
    "replicate": ["replicate", "replicata", "rep"],
    "date": ["date", "data", "analysisdate", "datadaanalise"],
    "laboratory": ["laboratory", "laboratorio", "lab"],
    "analysis_type": ["analysistype", "tipodeanalise"],
    "meta:batch": ["batch", "batchid"],
    "meta:lot": ["lot", "lote", "lotid"],
    "meta:genotype": ["genotype", "genotipo", "genotypeid"],
    "meta:cultivar": ["cultivar"],
    "meta:matrix": ["matrix", "matriz"],
    "meta:storage_time": ["storagetime", "tempodearmazenamento"],
    "meta:storage_condition": ["storagecondition", "condicaodearmazenamento"],
    "meta:sample_name": ["samplename", "nome", "nomedaamostra"],
    "meta:treatment": ["treatment", "tratamento"],
    "meta:processing": ["processing", "processamento"],
    "meta:timepoint": ["timepoint", "tempo"],
    "meta:notes": ["notes", "observacoes", "obs"],
    "spectrum:instrument": ["instrument", "instrumento", "equipamento"],
    "spectrum:operator": ["operator", "operador"],
    "spectrum:acquisition_date": ["acquisitiondate", "datadeaquisicao"],
}
_ALIAS_TO_ROLE = {fold(alias): role for role, aliases in _ALIASES.items() for alias in aliases}
_UNIT_IN_HEADER = re.compile(r"^(?P<name>.*?)\s*[\(\[](?P<unit>[^\)\]]+)[\)\]]\s*$")


def split_header_unit(header: str) -> tuple[str, str | None]:
    """``"TBARS (mg MDA/kg)"`` → ``("TBARS", "mg MDA/kg")``."""
    match = _UNIT_IN_HEADER.match(header.strip())
    if match and match.group("name"):
        return match.group("name").strip(), match.group("unit").strip()
    return header.strip(), None


def validate_role(role: str, vocabulary: Vocabulary) -> None:
    if role in SIMPLE_ROLES:
        return
    if role.startswith(META_PREFIX) and role[len(META_PREFIX):] in SAMPLE_FIELDS:
        return
    if role.startswith(SPECTRUM_PREFIX) and role[len(SPECTRUM_PREFIX):] in SPECTRUM_FIELDS:
        return
    if role.startswith(REFERENCE_PREFIX) and role[len(REFERENCE_PREFIX):] in vocabulary.parameters:
        return
    raise ConfigurationError(f"papel de coluna desconhecido: {role!r}")


def suggest_role(header: str, decimal: str, vocabulary: Vocabulary) -> str:
    name, _unit = split_header_unit(header)
    if to_float(name, decimal) is not None:
        return SPECTRAL
    key = fold(name)
    if key in _ALIAS_TO_ROLE:
        return _ALIAS_TO_ROLE[key]
    spec = vocabulary.resolve_parameter(name)
    if spec is not None:
        return f"{REFERENCE_PREFIX}{spec.name}"
    return IGNORE


def suggest_mapping(columns: list[str], decimal: str, vocabulary: Vocabulary,
                    has_header: bool) -> dict[str, str]:
    """Sugestão por coluna. Sem cabeçalho e com duas colunas: comprimento de onda e sinal."""
    if not has_header:
        if len(columns) == 2:
            return {columns[0]: WAVELENGTH, columns[1]: SIGNAL}
        return {column: IGNORE for column in columns}
    mapping: dict[str, str] = {}
    used_single: set[str] = set()
    for column in columns:
        role = suggest_role(column, decimal, vocabulary)
        if role not in (SPECTRAL, IGNORE) and role in used_single:
            role = IGNORE  # segundo candidato ao mesmo papel: o usuário decide
        if role not in (SPECTRAL, IGNORE):
            used_single.add(role)
        mapping[column] = role
    return mapping
