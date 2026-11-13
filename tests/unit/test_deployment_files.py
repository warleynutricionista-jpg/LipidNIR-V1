"""Coerência dos arquivos de implantação. A execução real com Podman não é coberta aqui."""

from pathlib import Path

import yaml

import lipidence_modular

DEPLOY = Path(lipidence_modular.__file__).resolve().parent / "deployment"


def test_compose_declares_app_and_postgres_only():
    compose = yaml.safe_load((DEPLOY / "compose.yaml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"app", "db"}
    assert compose["services"]["db"]["image"].startswith("docker.io/library/postgres:")
    app = compose["services"]["app"]
    assert app["depends_on"]["db"]["condition"] == "service_healthy"
    assert (DEPLOY / app["build"]["context"] / app["build"]["dockerfile"]).resolve() == (
        DEPLOY / "Containerfile"
    )
    env = app["environment"]
    assert env["LIPIDENCE_DATABASE_URL"].startswith("postgresql+psycopg2://")
    assert "LIPIDENCE_STORAGE_DIR" in env


def test_compose_has_no_hardcoded_password():
    text = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
    assert "${LIPIDENCE_DB_PASSWORD:?" in text
    compose = yaml.safe_load(text)
    assert compose["services"]["db"]["environment"]["POSTGRES_PASSWORD"].startswith("${")


def test_containerfile_runs_unprivileged_and_migrates_before_serving():
    text = (DEPLOY / "Containerfile").read_text(encoding="utf-8")
    assert "\nUSER lipidence" in text
    assert text.index("db upgrade") < text.index("serve --host")
    assert "requirements.txt" in text
