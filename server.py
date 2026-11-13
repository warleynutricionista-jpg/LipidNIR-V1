"""Composição final: API e, opcionalmente, a interface Dash na mesma instância FastAPI.

``uvicorn --factory lipidence_modular.server:create_app`` ou
``python -m lipidence_modular serve``.
"""

from __future__ import annotations

from fastapi import FastAPI

from lipidence_modular.api.app import create_api
from lipidence_modular.application.context import AppContext, build_context


def create_app(context: AppContext | None = None, *, with_ui: bool = True) -> FastAPI:
    context = context or build_context()
    app = create_api(context)
    if with_ui:
        # Import tardio: a API e a CLI funcionam sem o Dash instalado (INV-13).
        from lipidence_modular.ui.dash.app import attach_dash

        attach_dash(app, context)
    return app


def create_api_only() -> FastAPI:
    return create_app(with_ui=False)
