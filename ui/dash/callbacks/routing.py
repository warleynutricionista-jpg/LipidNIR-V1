"""Roteamento entre as três telas."""

from __future__ import annotations

from collections.abc import Sequence

from dash import Dash, Input, Output, html

from lipidence_modular.ui.dash.gateway import Gateway


def resolve_page(pathname: str | None, base_path: str, pages: Sequence):
    """Página correspondente ao caminho, ou ``None`` quando não existe."""
    if not pathname or not pathname.startswith(base_path.rstrip("/")):
        return None
    slug = pathname[len(base_path.rstrip("/")):].strip("/")
    if slug == "":
        return pages[0]
    for page in pages:
        if page.SLUG == slug:
            return page
    return None


def render_page(pathname: str | None, base_path: str, pages: Sequence):
    page = resolve_page(pathname, base_path, pages)
    if page is None:
        return html.Div(
            [html.H2("Página não encontrada"), html.P(f"Não existe tela em {pathname!r}.")],
            className="page",
        )
    return page.layout()


def session_label(gateway: Gateway) -> str:
    session = gateway.current_session()
    if session is None:
        return ""
    return f"{session.user.username} ({session.user.role.value})"


def register(app: Dash, gateway: Gateway, pages: Sequence) -> None:
    @app.callback(
        Output("page-content", "children"),
        Output("session-user", "children"),
        Input("url", "pathname"),
    )
    def _route(pathname):
        return render_page(pathname, gateway.base_path, pages), session_label(gateway)
