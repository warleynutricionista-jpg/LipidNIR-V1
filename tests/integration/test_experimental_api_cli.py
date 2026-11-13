"""Base experimental pela API e pela CLI (os mesmos serviços da interface)."""

from __future__ import annotations

import io

import pytest
import yaml
from fastapi.testclient import TestClient

from lipidence_modular.application.contracts import CreateUserInput
from lipidence_modular.auth.roles import Role
from lipidence_modular.cli.main import main
from lipidence_modular.server import create_app
from lipidence_modular.tests.fixtures import synthetic
from lipidence_modular.tests.integration.test_auth_flow import PASSWORD, do_login

pytestmark = pytest.mark.db

DATA = synthetic.make_set(3, 2, seed=1)
PLAN = {"signal_type": "absorbance", "wavelength_unit": "nm"}


@pytest.fixture()
def client(context):
    context.auth.create_user(CreateUserInput(username="ana", password=PASSWORD, role=Role.USER))
    with TestClient(create_app(context, with_ui=False), follow_redirects=False) as c:
        do_login(c, "ana")
        c.headers["X-CSRFToken"] = c.cookies.get("_csrf_token")
        yield c


def stage(client, content, name, kind, study="E1"):
    return client.post("/api/imports", files={"file": (name, io.BytesIO(content))},
                       data={"kind": kind, "study_id": study})


def test_import_flow_through_the_api(client):
    response = stage(client, synthetic.wide_csv(DATA, references=True), "c.csv", "combined")
    assert response.status_code == 201, response.text
    staged = response.json()
    batch = staged["import_batch_id"]
    assert staged["detection"]["decimal"] == ","

    preview = client.post(f"/api/imports/{batch}/preview", json=PLAN).json()
    assert preview["ok"] and preview["report"]["received"] == 6
    assert client.get("/api/base/summary").json()["samples"] == 0  # preview não grava

    report = client.post(f"/api/imports/{batch}/confirm", json=PLAN).json()
    assert (report["imported"], report["spectra_written"], report["references_written"]) == (
        6, 6, 12)
    assert client.get(f"/api/imports/{batch}").json()["status"] == "IMPORTED"
    assert client.get("/api/base/summary").json()["complete_samples"] == 6
    listed = client.get("/api/samples", params={"genotype": "G01"}).json()
    assert [s["sample_id"] for s in listed["samples"]] == ["S001", "S002"]
    assert client.get("/api/base/filters").json()["genotypes"] == ["G01", "G02", "G03"]


def test_api_error_mapping(client):
    assert client.get("/api/imports/nao-existe").status_code == 404
    assert stage(client, b"x", "x.jdx", "spectra").status_code == 422
    assert stage(client, b"a;b\n1;2\n", "x.csv", "inventado").status_code == 422
    batch = stage(client, synthetic.wide_csv(DATA), "a.csv", "spectra").json()["import_batch_id"]
    missing = client.post(f"/api/imports/{batch}/confirm", json={})
    assert missing.status_code == 422 and "signal_type" in missing.json()["detail"]
    assert client.post(f"/api/imports/{batch}/confirm", json={"opcao": 1}).status_code == 422
    assert client.post(f"/api/imports/{batch}/confirm", json=PLAN).status_code == 200
    assert client.post(f"/api/imports/{batch}/confirm", json=PLAN).status_code == 409
    again = stage(client, synthetic.wide_csv(DATA), "a.csv", "spectra").json()
    duplicate = client.post(f"/api/imports/{again['import_batch_id']}/confirm", json=PLAN)
    assert duplicate.status_code == 409 and duplicate.json()["duplicate_of"] == batch
    assert client.get("/api/samples", params={"completeness": "talvez"}).status_code == 422


def test_identity_conflict_is_409_with_candidates(client):
    one = synthetic.make_set(1, 1, seed=3)
    one.sample_ids = ["A001"]
    batch = stage(client, synthetic.wide_csv(one), "a.csv", "spectra").json()["import_batch_id"]
    response = client.post(f"/api/imports/{batch}/confirm",
                           json={**PLAN, "user_sample_id": "A002"})
    assert response.status_code == 409
    assert response.json()["conflict"]["candidates"] == {"FILE": "A001", "USER_ENTERED": "A002"}
    ok = client.post(f"/api/imports/{batch}/confirm",
                     json={**PLAN, "user_sample_id": "A002", "conflict_confirmed": True})
    assert ok.status_code == 200


def test_manual_registration_and_templates_through_the_api(client):
    created = client.post("/api/samples", json={
        "study_id": "E1", "sample_id": "m-01", "metadata": {"genotype": "G9"}})
    assert created.status_code == 201 and created.json() == {"sample_id": "M-01"}
    reference = client.post("/api/references", json={
        "study_id": "E1", "sample_id": "M-01", "parameter": "PV", "value": 2.5,
        "unit": "meq O₂/kg"})
    assert reference.status_code == 201 and reference.json() == {"replicate": 1}
    assert client.post("/api/samples", json={"study_id": "E1", "sample_id": "m-01"}
                       ).status_code == 422
    template = {"name": "GC-FID", "kind": "reference", "plan": {"decimal": ","}}
    assert client.post("/api/templates", json=template).status_code == 201
    assert [t["name"] for t in client.get("/api/templates").json()] == ["GC-FID"]


def test_experimental_routes_require_session(context):
    with TestClient(create_app(context, with_ui=False), follow_redirects=False) as c:
        assert c.get("/api/base/summary").status_code == 401
        assert c.get("/api/samples").status_code == 401
        assert stage(c, b"a;b\n1;2\n", "x.csv", "spectra").status_code == 401


def test_cli_import_preview_then_confirm_and_query(context, tmp_path, monkeypatch, capsys):
    context.auth.create_user(CreateUserInput(username="ana", password=PASSWORD, role=Role.USER))
    monkeypatch.setenv("LIPIDENCE_DATABASE_URL", context.settings.database_url)
    monkeypatch.setenv("LIPIDENCE_STORAGE_DIR", str(context.settings.storage_dir))
    data_file = tmp_path / "combinado.csv"
    data_file.write_bytes(synthetic.wide_csv(DATA, references=True))
    plan_file = tmp_path / "plano.yaml"
    plan_file.write_text(yaml.safe_dump(PLAN))
    base = ["import", "run", "--file", str(data_file), "--kind", "combined", "--study", "E1",
            "--as-user", "ana"]

    assert main(base) == 2  # sem plano: declarações obrigatórias ausentes
    assert "BLOQUEADO" in capsys.readouterr().out

    assert main([*base, "--plan", str(plan_file)]) == 0
    out = capsys.readouterr().out
    assert "Arquivos recebidos: 6" in out and "PREVIEW: nada foi gravado" in out
    assert context.base.summary().samples == 0

    assert main([*base, "--plan", str(plan_file), "--confirm"]) == 0
    assert "Importados: 6" in capsys.readouterr().out
    assert context.base.summary().complete_samples == 6

    assert main([*base, "--plan", str(plan_file), "--confirm"]) == 2  # mesmo arquivo de novo
    captured = capsys.readouterr()
    assert "AVISO: arquivo já importado" in captured.out and "nada foi duplicado" in captured.err

    assert main(["base", "summary", "--study", "E1"]) == 0
    assert '"complete_samples": 6' in capsys.readouterr().out
    assert main(["base", "samples", "--genotype", "G02"]) == 0
    out = capsys.readouterr().out
    assert "total: 2" in out and "S003" in out and "C18:2,TBARS" in out

    assert main([*base[:-1], "ninguem"]) == 2
    assert "usuário inexistente" in capsys.readouterr().err
