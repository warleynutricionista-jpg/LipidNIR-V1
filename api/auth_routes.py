"""Rotas de autenticação: login, logout e sessão corrente."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from lipidence_modular.api import pages
from lipidence_modular.application.auth_service import InvalidCredentialsError
from lipidence_modular.application.context import AppContext
from lipidence_modular.application.contracts import AuthenticatedSession, UserOut
from lipidence_modular.auth.tokens import new_token, tokens_match

LOGIN_CSRF_COOKIE = "lm_login_csrf"


def current_session(request: Request) -> AuthenticatedSession:
    session = getattr(request.state, "auth", None)
    if session is None:
        raise HTTPException(status_code=401, detail="sessão ausente ou expirada")
    return session


def build_auth_router(context: AppContext) -> APIRouter:
    settings = context.settings
    router = APIRouter()

    def _login_form(status_code: int, error: str | None = None) -> HTMLResponse:
        token = new_token()
        response = HTMLResponse(pages.login_page(token, error), status_code=status_code)
        response.set_cookie(
            LOGIN_CSRF_COOKIE, token, httponly=True, samesite="strict",
            secure=settings.cookie_secure, max_age=900, path="/login",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_form(request: Request) -> Response:
        if getattr(request.state, "auth", None) is not None:
            return RedirectResponse(settings.dash_prefix, status_code=303)
        return _login_form(200)

    @router.post("/login", include_in_schema=False)
    def login_submit(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        csrf_token: Annotated[str, Form()],
    ) -> Response:
        if not tokens_match(csrf_token, request.cookies.get(LOGIN_CSRF_COOKIE)):
            return _login_form(403, "Formulário expirado. Tente novamente.")
        try:
            result = context.auth.login(username, password)
        except InvalidCredentialsError:
            return _login_form(401, "Usuário ou senha inválidos.")
        max_age = settings.session_ttl_minutes * 60
        response = RedirectResponse(settings.dash_prefix, status_code=303)
        response.set_cookie(
            settings.session_cookie_name, result.token, httponly=True, samesite="lax",
            secure=settings.cookie_secure, max_age=max_age, path="/",
        )
        # Lido pelo renderer do Dash e por clientes da API para montar o cabeçalho CSRF.
        response.set_cookie(
            settings.csrf_cookie_name, result.session.csrf_token, httponly=False,
            samesite="lax", secure=settings.cookie_secure, max_age=max_age, path="/",
        )
        response.delete_cookie(LOGIN_CSRF_COOKIE, path="/login")
        return response

    @router.get("/logout", response_class=HTMLResponse, include_in_schema=False)
    def logout_form(request: Request) -> Response:
        session = getattr(request.state, "auth", None)
        if session is None:
            return RedirectResponse("/login", status_code=303)
        html = pages.logout_page(session.csrf_token, session.user.username, settings.dash_prefix)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @router.post("/logout", include_in_schema=False)
    def logout_submit(request: Request, csrf_token: Annotated[str, Form()] = "") -> Response:
        session = getattr(request.state, "auth", None)
        if session is not None:
            sent = csrf_token or request.headers.get(settings.csrf_header_name)
            if not tokens_match(sent, session.csrf_token):
                raise HTTPException(status_code=403, detail="token CSRF ausente ou inválido")
            context.auth.logout(request.cookies.get(settings.session_cookie_name))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(settings.session_cookie_name, path="/")
        response.delete_cookie(settings.csrf_cookie_name, path="/")
        return response

    @router.get("/api/auth/me", response_model=UserOut)
    def me(request: Request) -> UserOut:
        return current_session(request).user

    return router
