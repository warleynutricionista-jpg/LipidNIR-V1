"""Tela: Predição."""

from __future__ import annotations

from dash import html

from lipidence_modular.ui.dash.components.page_frame import page_frame

SLUG = "predicao"
TITLE = "Predição"
SUMMARY = "Nova amostra, processamento, aplicação dos modelos ativos e resultados."


def layout() -> html.Div:
    return page_frame(
        TITLE,
        SUMMARY,
        [html.P("Nenhuma função desta tela foi implementada até a fase atual.", className="note")],
    )
