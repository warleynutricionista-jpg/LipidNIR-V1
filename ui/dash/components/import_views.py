"""Peças da importação: mapeamento, relatório e mensagens."""

from __future__ import annotations

from dash import dcc, html

from lipidence_modular.ui.dash.components.figures import spectra_figure

LEVEL_LABELS = {"ALERT": "Alerta", "REJECTED": "Rejeitado"}


def message(text: str, kind: str = "info") -> html.Div:
    return html.Div(text, className=f"msg msg-{kind}", role="alert" if kind == "error" else None)


def detection_summary(staged) -> html.Div:
    d = staged.detection
    parts = [f"formato {d.file_format}"]
    if d.delimiter is not None:
        parts += [f"delimitador {d.delimiter!r}", f"separador decimal {d.decimal!r}"]
    if d.sheet:
        parts.append(f"aba {d.sheet!r}")
    parts.append("com cabeçalho" if d.has_header else "sem cabeçalho")
    children = [
        html.P([html.Strong(staged.original_filename), f" — detectado: {', '.join(parts)}."]),
        html.P(f"SHA-256: {staged.file_hash}", className="hint mono"),
    ]
    if staged.duplicate_of:
        children.append(message(
            f"Este arquivo já foi importado neste estudo (lote {staged.duplicate_of}). "
            "A importação não será duplicada.", "warn"))
    children += [message(note, "warn") for note in staged.notes]
    return html.Div(children)


def report_view(report, title: str) -> html.Div:
    counts = html.Div([
        html.Div([html.Span(str(value), className="count-value"),
                  html.Span(label, className="count-label")], className="count")
        for label, value in (("Recebidos", report.received), ("Importados", report.imported),
                             ("Alertas", report.alerts), ("Rejeitados", report.rejected))
    ], className="counts")
    lines = [
        html.Tr([html.Td(line.item), html.Td(LEVEL_LABELS.get(line.level, line.level)),
                 html.Td(line.message)], className=f"line-{line.level.lower()}")
        for line in report.lines
    ]
    body = [html.H4(title), counts,
            html.P(f"Espectros: {report.spectra_written} · Referências: "
                   f"{report.references_written} · Amostras novas: {report.samples_created}",
                   className="hint")]
    body += [message(note, "warn") for note in report.notes]
    if lines:
        body.append(html.Table(
            [html.Thead(html.Tr([html.Th("Item"), html.Th("Situação"), html.Th("Motivo")])),
             html.Tbody(lines)], className="report-table"))
    return html.Div(body, className="report")


def preview_view(preview) -> html.Div:
    if preview.blocking_error:
        children = [message(preview.blocking_error, "error")]
        if preview.conflict:
            candidates = ", ".join(f"{k}: {v}" for k, v in preview.conflict.candidates.items())
            children.append(message(
                f"CONFLITO DE IDENTIFICAÇÃO ({candidates}). Para seguir com o valor informado, "
                "marque “Confirmo o sample_id informado” e pré-visualize de novo.", "warn"))
        return html.Div(children)
    children = []
    if preview.duplicate_of:
        children.append(message(
            f"Arquivo já importado (lote {preview.duplicate_of}); a confirmação será recusada.",
            "warn"))
    if preview.ignored_columns:
        children.append(message(
            "Colunas que não serão importadas: " + ", ".join(preview.ignored_columns), "info"))
    children.append(report_view(preview.report, "Pré-visualização (nada foi gravado)"))
    if preview.spectra:
        children.append(dcc.Graph(figure=spectra_figure(preview.spectra),
                                  config={"displaylogo": False}))
    return html.Div(children)
