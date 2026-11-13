import json
import subprocess
import sys
from pathlib import Path

import pytest

import lipidence_modular
from lipidence_modular.cli.main import main

REPO_ROOT = Path(lipidence_modular.__file__).resolve().parent.parent


def test_version_command_prints_package_version(capsys):
    assert main(["version", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lipidence_modular"] == lipidence_modular.__version__


def test_module_entrypoint_runs_as_subprocess():
    proc = subprocess.run(
        [sys.executable, "-m", "lipidence_modular", "version"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert lipidence_modular.__version__ in proc.stdout


def test_unknown_command_is_an_explicit_error():
    with pytest.raises(SystemExit) as exc:
        main(["comando-que-nao-existe"])
    assert exc.value.code != 0
