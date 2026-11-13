"""Protocolo, regra 2: lipidence_modular não importa nada do sistema legado."""

import ast
from pathlib import Path

import lipidence_modular

PKG = Path(lipidence_modular.__file__).resolve().parent
FORBIDDEN_ROOTS = {"backend", "app"}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"import relativo em {path} (use imports absolutos)"
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_module_imports_legacy_backend_and_imports_are_absolute():
    files = list(PKG.rglob("*.py"))
    assert files
    offenders = {
        str(f.relative_to(PKG)): sorted(_imported_roots(f) & FORBIDDEN_ROOTS)
        for f in files
        if _imported_roots(f) & FORBIDDEN_ROOTS
    }
    assert not offenders, offenders
