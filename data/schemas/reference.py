from __future__ import annotations

from dataclasses import dataclass, field

from lipidence_modular.data.identity.resolution import FieldOrigin


@dataclass
class ParsedReference:
    """Uma medida de referência: amostra × parâmetro × replicata (formato longo)."""

    item: str
    sample_id: str
    sample_id_raw: str
    sample_id_origin: FieldOrigin
    parameter: str
    value: float
    unit: str
    replicate: int | None = None
    analysis_type: str | None = None
    method: str | None = None
    date: str | None = None
    laboratory: str | None = None
    sample_metadata: dict[str, str] = field(default_factory=dict)
    metadata_origins: dict[str, str] = field(default_factory=dict)
