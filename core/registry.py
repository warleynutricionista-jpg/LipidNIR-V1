"""Registry por manifestos.

Um componente (pré-processamento, modelo, atribuidor) é uma pasta com ``manifest.yaml``.
Acrescentar um componente = acrescentar uma pasta; nada mais é editado (seção 11.2).

O manifesto declara ``id`` e ``entrypoint`` (``modulo:Classe`` relativo à pasta, ex.:
``model:PLS1Regressor``). O registry valida os campos obrigatórios do tipo de componente
e importa a classe sob demanda.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lipidence_modular.core.errors import RegistryError


@dataclass(frozen=True)
class RegistryEntry:
    id: str
    kind: str
    directory: Path
    package: str
    manifest: dict[str, Any]

    def load_class(self) -> type:
        entrypoint = self.manifest["entrypoint"]
        module_name, _, class_name = entrypoint.partition(":")
        if not module_name or not class_name:
            raise RegistryError(
                f"{self.kind} '{self.id}': entrypoint {entrypoint!r} deve ser 'modulo:Classe'"
            )
        module = importlib.import_module(f"{self.package}.{module_name}")
        try:
            return getattr(module, class_name)
        except AttributeError as exc:
            raise RegistryError(
                f"{self.kind} '{self.id}': classe {class_name!r} não existe em {module.__name__}"
            ) from exc


class ManifestRegistry:
    """Descobre componentes de um tipo dentro de um pacote."""

    def __init__(self, kind: str, root: Path, package: str, required_fields: Iterable[str]):
        self.kind = kind
        self.root = Path(root)
        self.package = package
        self.required_fields = ("id", "entrypoint", *required_fields)
        self._entries: dict[str, RegistryEntry] | None = None

    def _discover(self) -> dict[str, RegistryEntry]:
        if not self.root.is_dir():
            raise RegistryError(f"diretório de {self.kind} inexistente: {self.root}")
        entries: dict[str, RegistryEntry] = {}
        for manifest_path in sorted(self.root.glob("*/manifest.yaml")):
            directory = manifest_path.parent
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise RegistryError(f"manifesto inválido (não é mapeamento): {manifest_path}")
            missing = [f for f in self.required_fields if f not in manifest]
            if missing:
                raise RegistryError(f"{manifest_path}: campos obrigatórios ausentes: {missing}")
            component_id = str(manifest["id"])
            if component_id != directory.name:
                raise RegistryError(
                    f"{manifest_path}: id {component_id!r} difere do nome da pasta "
                    f"{directory.name!r}"
                )
            if component_id in entries:
                raise RegistryError(f"{self.kind} duplicado: {component_id}")
            entries[component_id] = RegistryEntry(
                id=component_id,
                kind=self.kind,
                directory=directory,
                package=f"{self.package}.{directory.name}",
                manifest=manifest,
            )
        return entries

    @property
    def entries(self) -> dict[str, RegistryEntry]:
        if self._entries is None:
            self._entries = self._discover()
        return self._entries

    def ids(self) -> list[str]:
        return sorted(self.entries)

    def get(self, component_id: str) -> RegistryEntry:
        try:
            return self.entries[component_id]
        except KeyError:
            raise RegistryError(
                f"{self.kind} desconhecido: {component_id!r}. Disponíveis: {self.ids()}"
            ) from None

    def create(self, component_id: str, **params: Any) -> Any:
        cls = self.get(component_id).load_class()
        try:
            return cls(**params)
        except TypeError as exc:
            raise RegistryError(
                f"{self.kind} '{component_id}': parâmetros inválidos {sorted(params)}: {exc}"
            ) from exc
