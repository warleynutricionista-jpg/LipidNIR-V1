"""Casca do Dash sobre o FastAPI: três páginas, protegidas por sessão."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from lipidence_modular.application.contracts import CreateUserInput
from lipidence_modular.auth.roles import Role
from lipidence_modular.server import create_app
from lipidence_modular.tests.integration.test_auth_flow import PASSWORD, do_login
from lipidence_modular.ui.dash.callbacks.routing import render_page, resolve_page
from lipidence_modular.ui.dash.pages import PAGES

pytestmark = pytest.mark.db

PAGE_PATHS = ["/app/", "/app/base-experimental", "/app/predicao", "/app/desempenho"]
DASH_INTERNAL = ["/app/_dash-layout", "/app/_dash-dependencies"]


@pytest.fixture()
def client(context):
    context.auth.create_user(CreateUserInput(username="ana", password=PASSWORD, role=Role.USER))
    with TestClient(create_app(context), follow_redirects=False) as c:
        yield c


@pytest.mark.parametrize("path", PAGE_PATHS + DASH_INTERNAL)
def test_dash_routes_redirect_to_login_without_session(client, path):
    response = client.get(path)
    assert response.status_code == 303 and response.headers["location"] == "/login"


def test_dash_callback_endpoint_is_protected_without_session(client):
    response = client.post("/app/_dash-update-component", json={})
    assert response.status_code == 303 and response.headers["location"] == "/login"


@pytest.mark.parametrize("path", PAGE_PATHS + DASH_INTERNAL)
def test_dash_routes_are_served_with_session(client, path):
    do_login(client, "ana")
    assert client.get(path).status_code == 200


def test_layout_has_navigation_to_the_three_pages(client):
    do_login(client, "ana")
    layout = json.dumps(client.get("/app/_dash-layout").json(), ensure_ascii=False)
    for page in PAGES:
        assert f"/app/{page.SLUG}" in layout and page.TITLE in layout


def test_routing_callback_renders_page_and_user_through_the_server(client):
    do_login(client, "ana")
    body = {
        "output": "..page-content.children...session-user.children..",
        "outputs": [
            {"id": "page-content", "property": "children"},
            {"id": "session-user", "property": "children"},
        ],
        "inputs": [{"id": "url", "property": "pathname", "value": "/app/predicao"}],
        "changedPropIds": ["url.pathname"],
    }
    blocked = client.post("/app/_dash-update-component", json=body)
    assert blocked.status_code == 403  # sem cabeçalho CSRF
    response = client.post(
        "/app/_dash-update-component", json=body,
        headers={"X-CSRFToken": client.cookies.get("_csrf_token")},
    )
    assert response.status_code == 200, response.text
    payload = json.dumps(response.json(), ensure_ascii=False)
    assert "Predição" in payload and "ana (USER)" in payload


def test_api_works_without_the_interface(context):
    """INV-13: a API sobe e autentica sem o Dash."""
    context.auth.create_user(CreateUserInput(username="bia", password=PASSWORD, role=Role.USER))
    with TestClient(create_app(context, with_ui=False), follow_redirects=False) as c:
        assert do_login(c, "bia").status_code == 303
        assert c.get("/app/_dash-layout").status_code == 404
        assert c.get("/api/auth/me").json()["username"] == "bia"


def test_resolve_page_maps_paths_to_the_three_pages():
    assert resolve_page("/app/", "/app/", PAGES) is PAGES[0]
    assert resolve_page("/app", "/app/", PAGES) is PAGES[0]
    assert [resolve_page(f"/app/{p.SLUG}", "/app/", PAGES) for p in PAGES] == list(PAGES)
    assert resolve_page("/app/nao-existe", "/app/", PAGES) is None
    assert resolve_page(None, "/app/", PAGES) is None
    assert len(PAGES) == 3


def test_unknown_path_renders_not_found_message():
    assert "Página não encontrada" in str(render_page("/app/x", "/app/", PAGES))
