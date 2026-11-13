"""Tela Base Experimental: callbacks testados como funções (seção 20), contra os serviços
reais. A sessão do usuário é fornecida diretamente ao gateway."""

from __future__ import annotations

import base64

import pytest

from lipidence_modular.application.contracts import CreateUserInput
from lipidence_modular.auth.roles import Role
from lipidence_modular.tests.fixtures import synthetic
from lipidence_modular.ui.dash.callbacks import base_experimental as cb
from lipidence_modular.ui.dash.gateway import Gateway

pytestmark = pytest.mark.db

DATA = synthetic.make_set(3, 2, seed=1)
FORM = {"signal_type": "absorbance", "axis_unit": "nm", "scale": None, "user_sample_id": None,
        "reference_units": None, "matrix": "farinha", "instrument": None, "flags": []}


def upload(content: bytes) -> str:
    return "data:text/csv;base64," + base64.b64encode(content).decode()


def text_of(component) -> str:
    return str(component)


@pytest.fixture()
def gateway(context, monkeypatch):
    context.auth.create_user(
        CreateUserInput(username="ana", password="senha-de-teste-123", role=Role.USER))
    session = context.auth.login("ana", "senha-de-teste-123").session
    gw = Gateway(context)
    monkeypatch.setattr(gw, "current_session", lambda: session)
    return gw


def test_upload_preview_confirm_and_query(gateway):
    batch_id, staged_view, rows = cb.handle_upload(
        gateway, upload(synthetic.wide_csv(DATA, references=True)), "c.csv", "combined", "E1")
    assert batch_id and "separador decimal ','" in text_of(staged_view)
    assert rows[0] == {"column": "Sample", "role": "sample_id"}

    plan = cb.build_plan(mapping_rows=rows, **FORM)
    preview, wrote = cb.handle_import_action(gateway, "preview", batch_id, plan)
    assert not wrote and "nada foi gravado" in text_of(preview)
    assert gateway.summary().samples == 0

    done, wrote = cb.handle_import_action(gateway, "confirm", batch_id, plan)
    assert wrote and "Importação concluída" in text_of(done)
    cards = text_of(cb.summary_cards(gateway.summary()))
    assert "Completas" in cards and "'6'" in cards

    table = text_of(cb.handle_query(gateway, "E1", "G01", None, "complete"))
    assert "2 amostra(s)" in table and "S001" in table and "C18:2, TBARS" in table


def test_errors_are_shown_as_messages_not_exceptions(gateway):
    assert "Informe o estudo" in text_of(
        cb.handle_upload(gateway, upload(b"a;b\n1;2\n"), "x.csv", "spectra", " ")[1])
    assert "formato não suportado" in text_of(
        cb.handle_upload(gateway, upload(b"x"), "x.jdx", "spectra", "E1")[1])
    assert "Envie um arquivo" in text_of(cb.handle_import_action(gateway, "preview", None, {})[0])
    batch_id, _, rows = cb.handle_upload(
        gateway, upload(synthetic.wide_csv(DATA)), "a.csv", "spectra", "E1")
    form = {**FORM, "signal_type": None}
    blocked, wrote = cb.handle_import_action(
        gateway, "confirm", batch_id, cb.build_plan(mapping_rows=rows, **form))
    assert not wrote and "signal_type" in text_of(blocked)
    rows[0]["role"] = "papel-inventado"
    bad = cb.handle_import_action(
        gateway, "preview", batch_id, cb.build_plan(mapping_rows=rows, **FORM))[0]
    assert "papel de coluna desconhecido" in text_of(bad)
    assert "completude" in text_of(cb.handle_query(gateway, None, None, None, "talvez"))


def test_identity_conflict_is_shown_and_needs_the_checkbox(gateway):
    one = synthetic.make_set(1, 1, seed=3)
    one.sample_ids = ["A001"]
    batch_id, _, rows = cb.handle_upload(
        gateway, upload(synthetic.wide_csv(one)), "a.csv", "spectra", "E1")
    form = {**FORM, "user_sample_id": "A002"}
    view = cb.handle_import_action(
        gateway, "preview", batch_id, cb.build_plan(mapping_rows=rows, **form))[0]
    assert "CONFLITO DE IDENTIFICAÇÃO" in text_of(view) and "Confirmo o sample_id" in text_of(view)
    form["flags"] = ["conflict_confirmed"]
    _, wrote = cb.handle_import_action(
        gateway, "confirm", batch_id, cb.build_plan(mapping_rows=rows, **form))
    assert wrote and gateway.list_samples().samples[0].sample_id == "A002"


def test_manual_registration_handlers(gateway):
    view, wrote = cb.handle_manual_sample(gateway, "E1", " m-01 ", "G9", "", None)
    assert wrote and "Amostra M-01 cadastrada" in text_of(view)
    assert not cb.handle_manual_sample(gateway, "E1", "m-01", None, None, None)[1]
    view, wrote = cb.handle_manual_reference(gateway, "E1", "M-01", "TBARS", 0.8,
                                             "mg MDA/kg", None, "")
    assert wrote and "replicata 1" in text_of(view)
    view, wrote = cb.handle_manual_reference(gateway, "E1", "M-01", "TBARS", 0.8, "ppm", 2, "")
    assert not wrote and "unidade desconhecida" in text_of(view)
    assert not cb.handle_manual_reference(gateway, "E1", "M-01", None, None, "", None, "")[1]
    assert [p["name"] for p in gateway.parameters()][:2] == ["C16:0", "C18:0"]


def test_gateway_requires_a_session_for_writes(context):
    gw = Gateway(context)
    gw.current_session = lambda: None
    view = cb.handle_upload(gw, upload(b"a;b\n1;2\n"), "x.csv", "spectra", "E1")[1]
    assert "sessão expirada" in text_of(view)


def test_build_plan_and_reference_units_parsing():
    assert cb.parse_reference_units("C18:2=%; TBARS = mg MDA/kg; ;x") == {
        "C18:2": "%", "TBARS": "mg MDA/kg"}
    plan = cb.build_plan(mapping_rows=[{"column": "a", "role": ""}], signal_type=None,
                         axis_unit="cm-1", scale="percent", user_sample_id=" A1 ",
                         reference_units="PV=meq O2/kg", matrix=" ", instrument="FT-NIR",
                         flags=["convert", "replicates"])
    assert plan == {
        "convert_to_absorbance": True, "repeated_rows_are_replicates": True,
        "conflict_confirmed": False, "reference_units": {"PV": "meq O2/kg"},
        "columns": {"a": "ignore"}, "wavelength_unit": "cm-1", "signal_scale": "percent",
        "user_sample_id": "A1", "spectrum_defaults": {"instrument": "FT-NIR"}}
