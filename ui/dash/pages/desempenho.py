"""Tela: Desempenho e Diagnóstico."""

from __future__ import annotations

from dash import html

from lipidence_modular.ui.dash.components.page_frame import page_frame

SLUG = "desempenho"
TITLE = "Desempenho e Diagnóstico"
SUMMARY = "Métricas, gráficos, limitações e o que investigar."


def layout() -> html.Div:
    return page_frame(
        TITLE,
        SUMMARY,
        [html.P("Nenhuma função desta tela foi implementada até a fase atual.", className="note")],
    )
