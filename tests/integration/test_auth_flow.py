"""Autenticação pela API: login, cookie, sessão, papéis, CSRF e logout (seção 17)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from lipidence_modular.application.auth_service import (
    AuthService,
    PermissionDeniedError,
    UserAlreadyExistsError,
)
from lipidence_modular.application.contracts import CreateUserInput
from lipidence_modular.auth.roles import Role
from lipidence_modular.core.config import Settings
from lipidence_modular.repositories.database import session_scope
from lipidence_modular.repositories.tables.auth import SessionRow, UserRow
from lipidence_modular.server import create_app

pytestmark = pytest.mark.db

PASSWORD = "senha-de-teste-123"


@pytest.fixture()
def users(context):
    context.auth.create_user(CreateUserInput(username="Admin", password=PASSWORD, role=Role.ADMIN))
    context.auth.create_user(CreateUserInput(username="ana", password=PASSWORD, role=Role.USER))


@pytest.fixture()
def client(context, users):
    with TestClient(create_app(context), follow_redirects=False) as c:
        yield c


def do_login(client, username="admin", password=PASSWORD):
    page = client.get("/login")
    assert page.status_code == 200
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    return client.post(
        "/login", data={"username": username, "password": password, "csrf_token": token}
    )


def set_cookie_headers(response, name):
    return [h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")]


def test_health_is_public(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_sets_httponly_samesite_session_cookie_with_expiry(client):
    response = do_login(client)
    assert response.status_code == 303 and response.headers["location"] == "/app/"
    (cookie,) = set_cookie_headers(response, "lm_session")
    lowered = cookie.lower()
    assert "httponly" in lowered and "samesite=lax" in lowered and "max-age=28800" in lowered
    assert "secure" not in lowered  # ambiente de teste, sem HTTPS
    (csrf,) = set_cookie_headers(response, "_csrf_token")
    assert "httponly" not in csrf.lower()  # lido pelo renderer do Dash


def test_cookie_is_secure_in_production(context, users):
    prod = Settings(
        database_url=context.settings.database_url,
        storage_dir=context.settings.storage_dir,
        environment="production",
    )
    context.settings = prod
    with TestClient(create_app(context), follow_redirects=False, base_url="https://t") as c:
        (cookie,) = set_cookie_headers(do_login(c), "lm_session")
    assert "secure" in cookie.lower()


def test_session_token_is_stored_only_as_hash(client, context):
    do_login(client)
    token = client.cookies.get("lm_session")
    with session_scope(context.session_factory) as db:
        row = db.scalar(select(SessionRow))
        assert row.token_hash != token and len(row.token_hash) == 64
        assert PASSWORD not in db.scalar(select(UserRow.password_hash).limit(1))


def test_me_requires_session_and_returns_user(client):
    assert client.get("/api/auth/me").status_code == 401
    do_login(client)
    assert client.get("/api/auth/me").json() == {
        "id": client.get("/api/auth/me").json()["id"], "username": "admin", "role": "ADMIN",
    }


@pytest.mark.parametrize(
    ("username", "password"), [("admin", "senha-errada-999"), ("ninguem", PASSWORD)]
)
def test_invalid_credentials_give_same_generic_error(client, username, password):
    response = do_login(client, username, password)
    assert response.status_code == 401
    assert "Usuário ou senha inválidos." in response.text
    assert not set_cookie_headers(response, "lm_session")


def test_login_without_valid_csrf_token_is_refused(client):
    client.get("/login")
    response = client.post(
        "/login", data={"username": "admin", "password": PASSWORD, "csrf_token": "forjado"}
    )
    assert response.status_code == 403
    assert not set_cookie_headers(response, "lm_session")


def test_logout_revokes_session_on_the_server(client):
    do_login(client)
    stolen = client.cookies.get("lm_session")
    page = client.get("/logout")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post("/logout", data={"csrf_token": token})
    assert response.status_code == 303 and response.headers["location"] == "/login"
    client.cookies.set("lm_session", stolen)  # cookie antigo reapresentado
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_csrf_token_is_refused(client):
    do_login(client)
    assert client.post("/logout", data={}).status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_expired_session_is_rejected(client, context):
    do_login(client)
    with session_scope(context.session_factory) as db:
        db.execute(update(SessionRow).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert client.get("/api/auth/me").status_code == 401


def test_inactive_user_cannot_login_or_keep_session(client, context):
    do_login(client)
    with session_scope(context.session_factory) as db:
        db.execute(update(UserRow).where(UserRow.username == "admin").values(is_active=False))
    assert client.get("/api/auth/me").status_code == 401
    assert do_login(client).status_code == 401


def test_unsafe_api_request_requires_csrf_header(client):
    do_login(client)
    # Rota inexistente: o middleware barra antes do roteamento quando falta o cabeçalho.
    assert client.post("/api/qualquer").status_code == 403
    ok = client.post("/api/qualquer", headers={"X-CSRFToken": client.cookies.get("_csrf_token")})
    assert ok.status_code in (404, 405)  # passou pelo middleware; a rota não existe


def test_role_restriction(context, users):
    admin = context.auth.login("admin", PASSWORD).session
    user = context.auth.login("ana", PASSWORD).session
    AuthService.require_role(admin, Role.ADMIN)
    with pytest.raises(PermissionDeniedError):
        AuthService.require_role(user, Role.ADMIN)


def test_usernames_are_unique_case_insensitively(context, users):
    with pytest.raises(UserAlreadyExistsError):
        context.auth.create_user(
            CreateUserInput(username="ADMIN", password=PASSWORD, role=Role.USER)
        )


def test_there_is_no_open_registration_route(client):
    paths = set(client.app.openapi()["paths"])
    assert not [p for p in paths if "user" in p or "register" in p or "signup" in p]
    for path in ("/register", "/signup", "/cadastro", "/api/auth/register", "/api/users"):
        assert client.get(path).status_code in (303, 401)
        assert client.post(path, data={"username": "x", "password": "y" * 12}).status_code in (
            303, 401,
        )


def test_deny_by_default_unknown_paths_never_serve_content_without_session(client):
    """A rota coringa do Dash não pode expor a interface fora da sessão (ADM-008)."""
    for path in ("/qualquer", "/app/x/y", "/_dash-layout", "/docs", "/openapi.json"):
        response = client.get(path)
        assert response.status_code == 303 and response.headers["location"] == "/login", path
    assert client.get("/api/nao-existe").status_code == 401
