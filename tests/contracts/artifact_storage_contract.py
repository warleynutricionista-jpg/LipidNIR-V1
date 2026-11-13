"""Bateria do contrato ``ArtifactStorage``. Toda implementação herda desta classe e
fornece a fixture ``storage``."""

from __future__ import annotations

import hashlib

import pytest

from lipidence_modular.core.contracts import ArtifactRef
from lipidence_modular.core.errors import ArtifactIntegrityError, StorageError


class ArtifactStorageContract:
    def test_put_bytes_returns_sha256_and_size(self, storage):
        ref = storage.put_bytes("raw/a.csv", b"abc")
        assert ref == ArtifactRef("raw/a.csv", hashlib.sha256(b"abc").hexdigest(), 3)

    def test_roundtrip_bytes(self, storage):
        storage.put_bytes("raw/a.bin", b"\x00\x01\xff")
        assert storage.get_bytes("raw/a.bin") == b"\x00\x01\xff"

    def test_put_file_and_download(self, storage, tmp_path):
        source = tmp_path / "in.txt"
        source.write_bytes(b"conteudo")
        ref = storage.put_file("raw/in.txt", source)
        out = storage.download_to("raw/in.txt", tmp_path / "out" / "copy.txt")
        assert out.read_bytes() == b"conteudo"
        assert ref.sha256 == hashlib.sha256(b"conteudo").hexdigest()

    def test_exists_and_stat(self, storage):
        assert not storage.exists("x/y")
        ref = storage.put_bytes("x/y", b"1")
        assert storage.exists("x/y")
        assert storage.stat("x/y") == ref

    def test_same_content_is_idempotent(self, storage):
        assert storage.put_bytes("k", b"same") == storage.put_bytes("k", b"same")

    def test_artifacts_are_immutable(self, storage):
        storage.put_bytes("k", b"one")
        with pytest.raises(ArtifactIntegrityError):
            storage.put_bytes("k", b"two")
        assert storage.get_bytes("k") == b"one"

    def test_missing_key_is_an_error(self, storage):
        with pytest.raises(StorageError):
            storage.get_bytes("nao/existe")
        with pytest.raises(StorageError):
            storage.stat("nao/existe")

    @pytest.mark.parametrize("key", ["", "../fora", "a/../../b", "/abs", "a\\b", " a", "a//b"])
    def test_invalid_keys_are_rejected(self, storage, key):
        with pytest.raises(StorageError):
            storage.put_bytes(key, b"x")

    def test_list_keys_by_prefix_sorted(self, storage):
        for key in ("b/2", "a/1", "b/1"):
            storage.put_bytes(key, key.encode())
        assert storage.list_keys() == ["a/1", "b/1", "b/2"]
        assert storage.list_keys("b/") == ["b/1", "b/2"]
