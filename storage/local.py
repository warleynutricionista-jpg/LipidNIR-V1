"""``ArtifactStorage`` sobre o sistema de arquivos local.

Gravação atômica (arquivo temporário + ``os.replace``), chaves confinadas ao diretório
raiz e artefatos imutáveis.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from lipidence_modular.core.contracts import ArtifactRef, ArtifactStorage
from lipidence_modular.core.errors import ArtifactIntegrityError, StorageError

_CHUNK = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalArtifactStorage(ArtifactStorage):
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key != key.strip():
            raise StorageError(f"chave de artefato inválida: {key!r}")
        if "\\" in key or key.startswith("/"):
            raise StorageError(f"chave de artefato deve ser relativa e usar '/': {key!r}")
        parts = key.split("/")
        if any(part in ("", ".", "..") or part != part.strip() for part in parts):
            raise StorageError(f"chave de artefato fora do armazenamento: {key!r}")
        return self.root.joinpath(*parts)

    def _commit(self, key: str, tmp_path: Path, digest: str) -> ArtifactRef:
        target = self._path(key)
        if target.exists():
            existing = sha256_file(target)
            tmp_path.unlink(missing_ok=True)
            if existing != digest:
                raise ArtifactIntegrityError(
                    f"artefato imutável: '{key}' já existe com outro conteúdo "
                    f"(existente {existing[:12]}…, novo {digest[:12]}…)"
                )
            return ArtifactRef(key=key, sha256=existing, size_bytes=target.stat().st_size)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, target)
        return ArtifactRef(key=key, sha256=digest, size_bytes=target.stat().st_size)

    def _tmp(self) -> Path:
        tmp_dir = self.root / ".tmp"
        tmp_dir.mkdir(exist_ok=True)
        fd, name = tempfile.mkstemp(dir=tmp_dir)
        os.close(fd)
        return Path(name)

    def put_bytes(self, key: str, data: bytes) -> ArtifactRef:
        self._path(key)
        tmp_path = self._tmp()
        tmp_path.write_bytes(data)
        return self._commit(key, tmp_path, sha256_bytes(data))

    def put_file(self, key: str, source: Path) -> ArtifactRef:
        self._path(key)
        source = Path(source)
        if not source.is_file():
            raise StorageError(f"arquivo de origem inexistente: {source}")
        tmp_path = self._tmp()
        shutil.copyfile(source, tmp_path)
        return self._commit(key, tmp_path, sha256_file(tmp_path))

    def _existing(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise StorageError(f"artefato inexistente: {key!r}")
        return path

    def get_bytes(self, key: str) -> bytes:
        return self._existing(key).read_bytes()

    def download_to(self, key: str, destination: Path) -> Path:
        source = self._existing(key)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return destination

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def stat(self, key: str) -> ArtifactRef:
        path = self._existing(key)
        return ArtifactRef(key=key, sha256=sha256_file(path), size_bytes=path.stat().st_size)

    def list_keys(self, prefix: str = "") -> list[str]:
        keys = []
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root)
            if rel.parts[0] == ".tmp":
                continue
            key = rel.as_posix()
            if key.startswith(prefix):
                keys.append(key)
        return sorted(keys)
