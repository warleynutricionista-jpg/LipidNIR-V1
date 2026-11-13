import io

import pytest

from lipidence_modular.cli.main import main
from lipidence_modular.repositories import migrate
from lipidence_modular.repositories.database import make_engine

pytestmark = pytest.mark.db


@pytest.fixture()
def cli_env(clean_database, tmp_path, monkeypatch):
    monkeypatch.setenv("LIPIDENCE_DATABASE_URL", clean_database)
    monkeypatch.setenv("LIPIDENCE_STORAGE_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("LIPIDENCE_ENV", "test")
    return clean_database


def test_db_upgrade_then_create_first_admin_and_login(cli_env, monkeypatch, capsys, tmp_path):
    assert main(["db", "upgrade"]) == 0
    engine = make_engine(cli_env)
    assert migrate.current_revision(engine) == migrate.head_revision(cli_env)
    engine.dispose()

    monkeypatch.setattr("sys.stdin", io.StringIO("senha-do-admin-1\n"))
    assert main(["user", "create", "--username", "chefe", "--role", "ADMIN",
                 "--password-stdin"]) == 0
    assert "chefe (ADMIN)" in capsys.readouterr().out

    from lipidence_modular.application.context import build_context

    context = build_context()
    try:
        assert context.auth.login("chefe", "senha-do-admin-1").session.user.role == "ADMIN"
    finally:
        context.close()


def test_cli_reports_errors_with_nonzero_exit(cli_env, monkeypatch, capsys):
    main(["db", "upgrade"])
    monkeypatch.setattr("sys.stdin", io.StringIO("curta\n"))
    assert main(["user", "create", "--username", "x_y", "--role", "USER",
                 "--password-stdin"]) == 2
    assert "erro:" in capsys.readouterr().err


def test_missing_configuration_is_explicit(monkeypatch, capsys):
    monkeypatch.delenv("LIPIDENCE_DATABASE_URL", raising=False)
    assert main(["db", "current"]) == 2
    assert "LIPIDENCE_DATABASE_URL" in capsys.readouterr().err
