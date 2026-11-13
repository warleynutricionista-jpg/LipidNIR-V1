"""Cria o Dash sobre a instância FastAPI e registra as páginas (ADM-003)."""

from __future__ import annotations

from pathlib import Path

from dash import Dash, dcc, html
from fastapi import FastAPI

from lipidence_modular.application.context import AppContext
from lipidence_modular.ui.dash.callbacks import base_experimental, routing
from lipidence_modular.ui.dash.components.navigation import navigation
from lipidence_modular.ui.dash.gateway import Gateway
from lipidence_modular.ui.dash.pages import PAGES

ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def attach_dash(server: FastAPI, context: AppContext) -> Dash:
    prefix = context.settings.dash_prefix
    gateway = Gateway(context)
    app = Dash(
        "lipidence_modular.ui",
        server=server,
        routes_pathname_prefix=prefix,
        requests_pathname_prefix=prefix,
        assets_folder=str(ASSETS_DIR),
        title="Lipidence-NIR Modular",
        suppress_callback_exceptions=True,
        serve_locally=True,
    )
    app.layout = html.Div(
        [
            dcc.Location(id="url", refresh=False),
            navigation(prefix, PAGES),
            html.Div(id="page-content"),
        ]
    )
    routing.register(app, gateway, PAGES)
    base_experimental.register(app, gateway)
    return app
