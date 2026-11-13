"""Fábrica da aplicação FastAPI (sem interface)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from lipidence_modular import __version__
from lipidence_modular.api.auth_routes import build_auth_router
from lipidence_modular.api.experimental_routes import build_experimental_router
from lipidence_modular.api.session_middleware import SessionMiddleware
from lipidence_modular.application.context import AppContext
from lipidence_modular.application.errors import describe_error
from lipidence_modular.core.errors import LipidenceError
from lipidence_modular.data.ingestion.spectra import PlanError


def create_api(context: AppContext) -> FastAPI:
    app = FastAPI(title="Lipidence-NIR Modular", version=__version__)
    app.state.context = context
    app.add_middleware(SessionMiddleware, auth=context.auth, settings=context.settings)
    app.include_router(build_auth_router(context))
    app.include_router(build_experimental_router(context))

    async def domain_error(request: Request, exc: Exception) -> JSONResponse:
        info = describe_error(exc)
        if info is None:
            raise exc
        return JSONResponse({"detail": info.message, **info.extra}, status_code=info.status_code)

    app.add_exception_handler(LipidenceError, domain_error)
    app.add_exception_handler(PlanError, domain_error)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(context.settings.dash_prefix, status_code=303)

    return app
