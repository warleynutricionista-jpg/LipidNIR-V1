import sys
import textwrap

import pytest

from lipidence_modular.core.errors import RegistryError
from lipidence_modular.core.registry import ManifestRegistry

THING = "class Thing:\n    def __init__(self, k=1):\n        self.k = k\n"


def _component(root, name, manifest, code=THING):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "__init__.py").write_text("")
    (directory / "impl.py").write_text(code)
    (directory / "manifest.yaml").write_text(textwrap.dedent(manifest))
    return directory


@pytest.fixture()
def package(tmp_path, monkeypatch):
    root = tmp_path / "lm_fake_components"
    root.mkdir()
    (root / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield root
    for name in [m for m in sys.modules if m.startswith("lm_fake_components")]:
        del sys.modules[name]


def _registry(root):
    return ManifestRegistry("modelo", root, "lm_fake_components", required_fields=["name"])


def test_discovers_components_by_manifest_and_instantiates(package):
    _component(package, "alpha", "id: alpha\nname: Alpha\nentrypoint: impl:Thing\n")
    _component(package, "beta", "id: beta\nname: Beta\nentrypoint: impl:Thing\n")
    registry = _registry(package)
    assert registry.ids() == ["alpha", "beta"]
    assert registry.get("alpha").manifest["name"] == "Alpha"
    assert registry.create("beta", k=7).k == 7


def test_adding_a_folder_adds_a_component_without_other_edits(package):
    _component(package, "alpha", "id: alpha\nname: A\nentrypoint: impl:Thing\n")
    assert _registry(package).ids() == ["alpha"]
    _component(package, "gamma", "id: gamma\nname: G\nentrypoint: impl:Thing\n")
    assert _registry(package).ids() == ["alpha", "gamma"]


def test_inv07_unknown_component_is_explicit_error_listing_available(package):
    _component(package, "alpha", "id: alpha\nname: A\nentrypoint: impl:Thing\n")
    with pytest.raises(RegistryError, match="alpha"):
        _registry(package).get("nao_existe")


@pytest.mark.parametrize(
    "manifest",
    [
        "id: alpha\nentrypoint: impl:Thing\n",  # falta name
        "id: outro\nname: A\nentrypoint: impl:Thing\n",  # id difere da pasta
        "- lista\n",  # não é mapeamento
    ],
)
def test_invalid_manifest_is_rejected(package, manifest):
    _component(package, "alpha", manifest)
    with pytest.raises(RegistryError):
        _registry(package).ids()


@pytest.mark.parametrize("entrypoint", ["impl", "impl:Missing"])
def test_bad_entrypoint_is_rejected(package, entrypoint):
    _component(package, "alpha", f"id: alpha\nname: A\nentrypoint: {entrypoint}\n")
    with pytest.raises(RegistryError):
        _registry(package).create("alpha")


def test_invalid_parameters_are_rejected(package):
    _component(package, "alpha", "id: alpha\nname: A\nentrypoint: impl:Thing\n")
    with pytest.raises(RegistryError, match="parâmetros inválidos"):
        _registry(package).create("alpha", nao_existe=1)


def test_missing_root_is_an_error(tmp_path):
    with pytest.raises(RegistryError):
        ManifestRegistry("modelo", tmp_path / "x", "x", []).ids()
