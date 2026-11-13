"""Middleware ASGI de sessão, com negação por padrão.

Toda rota exige sessão válida, exceto a lista explícita ``PUBLIC_PATHS``. O Dash registra
uma rota coringa que devolve a página da interface para qualquer caminho desconhecido;
por isso a proteção não pode ser uma lista de prefixos protegidos (ADM-008).

- sem sessão válida: 401 em ``/api/``; redirecionamento para ``/login`` no restante;
- método que altera estado: exige o cabeçalho CSRF igual ao token da sessão.

A regra de autenticação vive aqui e em ``auth/``; o Dash não a implementa (seção 17).
"""

from __future__ import annotations

from http.cookies import SimpleCookie

import anyio
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from lipidence_modular.application.auth_service import AuthService
from lipidence_modular.auth.tokens import tokens_match
from lipidence_modular.core.config import Settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# /login e /logout fazem a própria verificação de CSRF (campo de formulário).
PUBLIC_PATHS = frozenset({"/api/health", "/login", "/logout"})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


def _cookie(scope: Scope, name: str) -> str | None:
    raw = _header(scope, b"cookie")
    if not raw:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        return None
    morsel = jar.get(name)
    return morsel.value if morsel else None


class SessionMiddleware:
    def __init__(self, app: ASGIApp, auth: AuthService, settings: Settings):
        self.app = app
        self.auth = auth
        self.settings = settings

    def _is_api(self, path: str) -> bool:
        return path.startswith("/api/")

    def _is_protected(self, path: str) -> bool:
        return path not in PUBLIC_PATHS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        token = _cookie(scope, self.settings.session_cookie_name)
        session = await anyio.to_thread.run_sync(self.auth.resolve, token)
        scope.setdefault("state", {})["auth"] = session

        if not self._is_protected(path):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            if session is None:
                await send({"type": "websocket.close", "code": 1008})
                return
            await self.app(scope, receive, send)
            return

        if session is None:
            if self._is_api(path):
                response = JSONResponse({"detail": "sessão ausente ou expirada"}, status_code=401)
            else:
                response = RedirectResponse("/login", status_code=303)
            await response(scope, receive, send)
            return

        if scope["method"] not in SAFE_METHODS:
            sent = _header(scope, self.settings.csrf_header_name.lower().encode("latin-1"))
            if not tokens_match(sent, session.csrf_token):
                response = JSONResponse({"detail": "token CSRF ausente ou inválido"}, 403)
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
