from __future__ import annotations

from collections.abc import Sequence

from dash import html
from dash.development.base_component import Component


def page_frame(title: str, summary: str, children: Sequence[Component]) -> html.Div:
    return html.Div(
        [html.H2(title), html.P(summary, className="summary"), *children], className="page"
    )
