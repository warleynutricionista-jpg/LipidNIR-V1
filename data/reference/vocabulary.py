"""Vocabulário controlado (``config/parameters.yaml``): nome canônico, aliases, unidades
aceitas e faixa plausível. Fora do vocabulário, só com mapeamento confirmado (INV-7)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from lipidence_modular.config import CONFIG_DIR
from lipidence_modular.core.errors import ConfigurationError

PARAMETERS_FILE = CONFIG_DIR / "parameters.yaml"
_STRIP = re.compile(r"[\s_\-:./]+")


def fold(text: str) -> str:
    """Chave de comparação de nomes: sem acento, caixa, espaços e pontuação comum."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _STRIP.sub("", ascii_text).lower()


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    label: str
    analysis_type: str
    units: tuple[str, ...]
    range_min: float | None
    range_max: float | None

    def in_plausible_range(self, value: float) -> bool:
        if self.range_min is not None and value < self.range_min:
            return False
        return not (self.range_max is not None and value > self.range_max)


class Vocabulary:
    def __init__(self, parameters: list[ParameterSpec], aliases: dict[str, str],
                 unit_aliases: dict[str, str], status: str):
        self.parameters = {p.name: p for p in parameters}
        self._aliases = aliases
        self._unit_aliases = unit_aliases
        self.status = status

    def names(self) -> list[str]:
        return list(self.parameters)

    def resolve_parameter(self, raw: object) -> ParameterSpec | None:
        name = self._aliases.get(fold(str(raw)))
        return self.parameters[name] if name else None

    def resolve_unit(self, spec: ParameterSpec, raw: object) -> str | None:
        """Unidade aceita para o parâmetro, ou ``None``. Só equivalência de grafia."""
        text = " ".join(str(raw).split())
        candidates = {text, self._unit_aliases.get(text, text)}
        for unit in spec.units:
            if unit in candidates or fold(unit) in {fold(c) for c in candidates}:
                return unit
        return None


def load_vocabulary(path: Path = PARAMETERS_FILE) -> Vocabulary:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    parameters, aliases = [], {}
    for entry in data["parameters"]:
        plausible = entry.get("plausible_range") or {}
        spec = ParameterSpec(
            name=entry["name"],
            label=entry["label"],
            analysis_type=entry["analysis_type"],
            units=tuple(entry["units"]),
            range_min=plausible.get("min"),
            range_max=plausible.get("max"),
        )
        if not spec.units:
            raise ConfigurationError(f"parâmetro {spec.name} sem unidade aceita")
        parameters.append(spec)
        for alias in (spec.name, *entry.get("aliases", [])):
            key = fold(alias)
            if aliases.get(key, spec.name) != spec.name:
                raise ConfigurationError(
                    f"alias {alias!r} aponta para {aliases[key]} e para {spec.name}"
                )
            aliases[key] = spec.name
    return Vocabulary(parameters, aliases, dict(data.get("unit_aliases") or {}),
                      str(data.get("status", "")))


@lru_cache(maxsize=1)
def default_vocabulary() -> Vocabulary:
    return load_vocabulary()
