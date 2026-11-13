"""Regras de arquitetura verificadas pelos imports (seções 6, 19.2 e 20; INV-13)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import lipidence_modular

PKG = Path(lipidence_modular.__file__).resolve().parent
REPO_ROOT = PKG.parent

# ui/ só fala com application/ (pelo gateway) e com os seus próprios módulos.
UI_ALLOWED = {"application", "ui"}
# Camadas que não podem conhecer nada acima delas.
SCIENCE = {"core", "data", "preprocessing", "models", "validation", "evaluation", "ood",
           "uncertainty", "xai", "coherence", "diagnostics", "prediction"}
ABOVE_SCIENCE = {"api", "ui", "cli", "application", "repositories", "server"}
WEB_LIBS = {"dash", "fastapi", "starlette", "plotly", "uvicorn", "sqlalchemy", "alembic"}


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _internal_layers(path: Path) -> set[str]:
    return {
        name.split(".")[1]
        for name in _imports(path)
        if name.startswith("lipidence_modular.") and len(name.split(".")) > 1
    }


def _files(layer: str) -> list[Path]:
    return [p for p in (PKG / layer).rglob("*.py") if "tests" not in p.parts]


def test_ui_imports_only_application_and_itself():
    offenders = {
        str(p.relative_to(PKG)): sorted(_internal_layers(p) - UI_ALLOWED)
        for p in _files("ui")
        if _internal_layers(p) - UI_ALLOWED
    }
    assert not offenders, offenders


def test_only_the_gateway_reaches_application_services_from_ui():
    """Callbacks, páginas e componentes passam pelo gateway; ``app.py`` só recebe o contexto."""
    allowed = {PKG / "ui" / "dash" / "gateway.py", PKG / "ui" / "dash" / "app.py"}
    offenders = [
        str(p.relative_to(PKG))
        for p in _files("ui")
        if p not in allowed and "application" in _internal_layers(p)
    ]
    assert not offenders, offenders


def test_ui_does_not_import_orm_or_database_libraries():
    offenders = {
        str(p.relative_to(PKG)): sorted(n for n in _imports(p) if n.split(".")[0] in
                                        {"sqlalchemy", "alembic", "psycopg2"})
        for p in _files("ui")
    }
    assert not {k: v for k, v in offenders.items() if v}


def test_scientific_core_does_not_depend_on_upper_layers_or_web_libraries():
    offenders = {}
    for layer in sorted(SCIENCE):
        if not (PKG / layer).is_dir():
            continue
        for path in _files(layer):
            bad = (_internal_layers(path) & ABOVE_SCIENCE) | {
                n for n in _imports(path) if n.split(".")[0] in WEB_LIBS
            }
            if bad:
                offenders[str(path.relative_to(PKG))] = sorted(bad)
    assert not offenders, offenders


def test_import_dash_resolves_to_the_library_not_to_ui_dash():
    import dash

    origin = Path(dash.__file__).resolve()
    assert PKG not in origin.parents
    assert hasattr(dash, "Dash")


def test_inv13_cli_and_core_run_without_importing_dash_or_fastapi():
    code = (
        "import sys\n"
        "from lipidence_modular.cli.main import main\n"
        "import lipidence_modular.core.contracts, lipidence_modular.core.registry\n"
        "import lipidence_modular.storage.local, lipidence_modular.jobs.in_process\n"
        "import lipidence_modular.data.identity.resolution\n"
        "assert main(['version']) == 0\n"
        "loaded = {m.split('.')[0] for m in sys.modules}\n"
        "assert not loaded & {'dash', 'fastapi', 'starlette', 'celery'}, loaded\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO_ROOT, check=False
    )
    assert proc.returncode == 0, proc.stderr


def test_every_package_directory_has_code():
    """Um diretório só nasce com código dentro (seção 6)."""
    skip = {"__pycache__", "assets", "versions", "docs", "config", "deployment", "fixtures"}
    empty = [
        str(d.relative_to(PKG))
        for d in PKG.rglob("*")
        if d.is_dir() and not (set(d.relative_to(PKG).parts) & skip)
        and not any(part.startswith(".") for part in d.relative_to(PKG).parts)
        and not any(d.glob("*.py"))
    ]
    assert not empty, empty
