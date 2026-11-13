"""Normalização mínima e documentada do ``sample_id`` (seção 8.2).

Regra: aparar espaços nas pontas, colapsar espaços internos em um e passar para maiúsculas.
Nada mais. Não há correspondência aproximada (INV-1): ``A001`` e ``A-001`` são amostras
diferentes. O valor original é sempre preservado em ``sample_id_raw``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lipidence_modular.core.errors import IdentityError

_WHITESPACE = re.compile(r"\s+")
MAX_LENGTH = 128


@dataclass(frozen=True)
class SampleIdentity:
    sample_id: str
    sample_id_raw: str


def normalize_sample_id(raw: object) -> SampleIdentity:
    if raw is None:
        raise IdentityError("sample_id ausente")
    if isinstance(raw, float) and raw != raw:  # NaN de planilha
        raise IdentityError("sample_id ausente")
    if isinstance(raw, bool):
        raise IdentityError(f"sample_id inválido: {raw!r}")
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)  # planilhas leem "17" como 17.0
    text = str(raw)
    normalized = _WHITESPACE.sub(" ", text.strip()).upper()
    if not normalized:
        raise IdentityError("sample_id vazio")
    if len(normalized) > MAX_LENGTH:
        raise IdentityError(f"sample_id com mais de {MAX_LENGTH} caracteres")
    return SampleIdentity(sample_id=normalized, sample_id_raw=text)


def same_sample(a: object, b: object) -> bool:
    """Vínculo só por identidade normalizada exata."""
    return normalize_sample_id(a).sample_id == normalize_sample_id(b).sample_id
