from __future__ import annotations

from collections.abc import Sequence

from dash import dcc, html


def navigation(base_path: str, pages: Sequence, logout_href: str = "/logout") -> html.Nav:
    links = [
        dcc.Link(page.TITLE, href=f"{base_path}{page.SLUG}", className="nav-link")
        for page in pages
    ]
    return html.Nav(
        [
            html.Span("Lipidence-NIR Modular", className="brand"),
            *links,
            html.Span(id="session-user", className="session-user"),
            html.A("Sair", href=logout_href, className="nav-link logout"),
        ],
        className="topbar",
    )
