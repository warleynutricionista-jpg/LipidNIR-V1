"""Callbacks da Base Experimental: validam a entrada de interface, chamam o gateway e
formatam a saída. Nenhuma regra de importação vive aqui."""

from __future__ import annotations

from typing import Any

from dash import Dash, Input, Output, State, ctx, dash_table, html, no_update

from lipidence_modular.ui.dash.components.import_views import (
    detection_summary,
    message,
    preview_view,
    report_view,
)
from lipidence_modular.ui.dash.gateway import Gateway, UserFacingError
from lipidence_modular.ui.dash.pages.base_experimental import SAMPLE_COLUMNS


def parse_reference_units(text: str | None) -> dict[str, str]:
    """``"C18:2=%; TBARS=mg MDA/kg"`` → ``{"C18:2": "%", "TBARS": "mg MDA/kg"}``."""
    units: dict[str, str] = {}
    for part in (text or "").split(";"):
        if "=" in part:
            name, unit = part.split("=", 1)
            if name.strip() and unit.strip():
                units[name.strip()] = unit.strip()
    return units


def build_plan(*, mapping_rows, signal_type, axis_unit, scale, user_sample_id,
               reference_units, matrix, instrument, flags) -> dict[str, Any]:
    """Monta o plano a partir do formulário. Campo vazio fica ausente: quem decide se ele
    é obrigatório é o serviço."""
    flags = flags or []
    plan: dict[str, Any] = {
        "convert_to_absorbance": "convert" in flags,
        "repeated_rows_are_replicates": "replicates" in flags,
        "conflict_confirmed": "conflict_confirmed" in flags,
        "reference_units": parse_reference_units(reference_units),
    }
    if mapping_rows:
        plan["columns"] = {row["column"]: (row.get("role") or "").strip() or "ignore"
                           for row in mapping_rows}
    for key, value in (("signal_type", signal_type), ("wavelength_unit", axis_unit),
                       ("signal_scale", scale)):
        if value:
            plan[key] = value
    if user_sample_id and user_sample_id.strip():
        plan["user_sample_id"] = user_sample_id.strip()
    if matrix and matrix.strip():
        plan["sample_defaults"] = {"matrix": matrix.strip()}
    if instrument and instrument.strip():
        plan["spectrum_defaults"] = {"instrument": instrument.strip()}
    return plan


def summary_cards(summary) -> list[html.Div]:
    items = (("Amostras", summary.samples), ("Espectros", summary.spectra),
             ("Com espectro", summary.samples_with_spectrum),
             ("Com referência", summary.samples_with_reference),
             ("Completas", summary.complete_samples))
    return [html.Div([html.Span(str(value), className="count-value"),
                      html.Span(label, className="count-label")], className="count")
            for label, value in items]


def samples_table(sample_list) -> html.Div:
    rows = [{**{key: getattr(sample, key) for key, _ in SAMPLE_COLUMNS},
             "parameters": ", ".join(sample.parameters) or "—",
             "complete": "sim" if sample.complete else "não"}
            for sample in sample_list.samples]
    shown = len(rows)
    caption = f"{sample_list.total} amostra(s)" + (
        f"; exibindo as primeiras {shown}" if shown < sample_list.total else "")
    return html.Div([
        html.P(caption, className="hint"),
        dash_table.DataTable(
            columns=[{"name": label, "id": key} for key, label in SAMPLE_COLUMNS], data=rows,
            page_size=20, sort_action="native",
            style_cell={"textAlign": "left", "fontFamily": "inherit", "padding": "4px 8px"},
            style_header={"fontWeight": "600"},
        ),
    ])


def handle_upload(gateway: Gateway, contents, filename, kind, study):
    """(import_batch_id, resumo da detecção, linhas do mapeamento)."""
    if not contents:
        return no_update, no_update, no_update
    if not (study or "").strip():
        return None, message("Informe o estudo (study_id) antes de enviar o arquivo.",
                             "error"), []
    try:
        staged = gateway.stage_upload(contents, filename or "", kind, study)
    except UserFacingError as exc:
        return None, message(str(exc), "error"), []
    rows = [{"column": c, "role": r} for c, r in staged.suggested_columns.items()]
    return staged.import_batch_id, detection_summary(staged), rows


def handle_import_action(gateway: Gateway, action: str, batch_id, plan: dict):
    """(conteúdo do resultado, houve gravação?)."""
    if not batch_id:
        return message("Envie um arquivo antes de pré-visualizar ou confirmar.", "error"), False
    try:
        if action == "confirm":
            report = gateway.confirm_import(batch_id, plan)
            return report_view(report, "Importação concluída"), True
        return preview_view(gateway.preview_import(batch_id, plan)), False
    except UserFacingError as exc:
        return message(str(exc), "error"), False


def handle_query(gateway: Gateway, study, genotype, lot, completeness):
    try:
        return samples_table(gateway.list_samples(
            study_id=study, genotype=genotype, lot=lot, completeness=completeness))
    except UserFacingError as exc:
        return message(str(exc), "error")


def handle_manual_sample(gateway: Gateway, study, sample_id, genotype, lot, matrix):
    metadata = {k: v.strip() for k, v in (("genotype", genotype), ("lot", lot),
                                          ("matrix", matrix)) if v and v.strip()}
    try:
        created = gateway.register_sample(
            study_id=(study or "").strip(), sample_id=sample_id or "", metadata=metadata)
    except UserFacingError as exc:
        return message(str(exc), "error"), False
    return message(f"Amostra {created} cadastrada.", "ok"), True


def handle_manual_reference(gateway: Gateway, study, sample_id, parameter, value, unit,
                            replicate, method):
    if value is None or not parameter:
        return message("Informe parâmetro e valor.", "error"), False
    try:
        number = gateway.register_reference(
            study_id=(study or "").strip(), sample_id=sample_id or "", parameter=parameter,
            value=value, unit=unit or "", replicate=int(replicate) if replicate else None,
            method=(method or "").strip() or None)
    except UserFacingError as exc:
        return message(str(exc), "error"), False
    return message(f"Valor registrado (replicata {number}).", "ok"), True


def register(app: Dash, gateway: Gateway) -> None:
    @app.callback(
        Output("import-batch-id", "data"), Output("import-staged", "children"),
        Output("import-mapping", "data"),
        Input("import-upload", "contents"),
        State("import-upload", "filename"), State("import-kind", "value"),
        State("import-study", "value"), prevent_initial_call=True,
    )
    def _upload(contents, filename, kind, study):
        return handle_upload(gateway, contents, filename, kind, study)

    @app.callback(
        Output("import-result", "children"),
        Output("base-refresh", "data", allow_duplicate=True),
        Input("import-preview-btn", "n_clicks"), Input("import-confirm-btn", "n_clicks"),
        State("import-batch-id", "data"), State("import-mapping", "data"),
        State("import-signal-type", "value"), State("import-axis-unit", "value"),
        State("import-scale", "value"), State("import-user-sample-id", "value"),
        State("import-reference-units", "value"), State("import-matrix", "value"),
        State("import-instrument", "value"), State("import-flags", "value"),
        State("base-refresh", "data"), prevent_initial_call=True,
    )
    def _import_action(_preview, _confirm, batch_id, mapping_rows, signal_type, axis_unit,
                       scale, user_sample_id, reference_units, matrix, instrument, flags,
                       refresh):
        action = "confirm" if ctx.triggered_id == "import-confirm-btn" else "preview"
        plan = build_plan(
            mapping_rows=mapping_rows, signal_type=signal_type, axis_unit=axis_unit,
            scale=scale, user_sample_id=user_sample_id, reference_units=reference_units,
            matrix=matrix, instrument=instrument, flags=flags)
        content, wrote = handle_import_action(gateway, action, batch_id, plan)
        return content, (refresh or 0) + 1 if wrote else no_update

    @app.callback(
        Output("base-summary", "children"), Output("query-study", "options"),
        Output("query-genotype", "options"), Output("query-lot", "options"),
        Output("manual-parameter", "options"),
        Input("base-refresh", "data"),
    )
    def _refresh(_counter):
        options = gateway.filter_options()
        parameters = [{"label": f"{p['name']} — {p['label']} ({', '.join(p['units'])})",
                       "value": p["name"]} for p in gateway.parameters()]
        return (summary_cards(gateway.summary()), options.studies, options.genotypes,
                options.lots, parameters)

    @app.callback(
        Output("query-result", "children"),
        Input("query-btn", "n_clicks"), Input("base-refresh", "data"),
        State("query-study", "value"), State("query-genotype", "value"),
        State("query-lot", "value"), State("query-completeness", "value"),
    )
    def _query(_clicks, _counter, study, genotype, lot, completeness):
        return handle_query(gateway, study, genotype, lot, completeness)

    @app.callback(
        Output("manual-sample-result", "children"),
        Output("base-refresh", "data", allow_duplicate=True),
        Input("manual-sample-btn", "n_clicks"),
        State("manual-study", "value"), State("manual-sample-id", "value"),
        State("manual-genotype", "value"), State("manual-lot", "value"),
        State("manual-matrix", "value"), State("base-refresh", "data"),
        prevent_initial_call=True,
    )
    def _manual_sample(_clicks, study, sample_id, genotype, lot, matrix, refresh):
        content, wrote = handle_manual_sample(gateway, study, sample_id, genotype, lot, matrix)
        return content, (refresh or 0) + 1 if wrote else no_update

    @app.callback(
        Output("manual-reference-result", "children"),
        Output("base-refresh", "data", allow_duplicate=True),
        Input("manual-reference-btn", "n_clicks"),
        State("manual-study", "value"), State("manual-sample-id", "value"),
        State("manual-parameter", "value"), State("manual-value", "value"),
        State("manual-unit", "value"), State("manual-replicate", "value"),
        State("manual-method", "value"), State("base-refresh", "data"),
        prevent_initial_call=True,
    )
    def _manual_reference(_clicks, study, sample_id, parameter, value, unit, replicate, method,
                          refresh):
        content, wrote = handle_manual_reference(
            gateway, study, sample_id, parameter, value, unit, replicate, method)
        return content, (refresh or 0) + 1 if wrote else no_update
