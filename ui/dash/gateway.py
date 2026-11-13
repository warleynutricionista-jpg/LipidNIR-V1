"""Ponto único de acesso da interface aos serviços de ``application/`` (seção 19.2).

Nada em ``ui/`` importa módulos científicos, orquestrador, repositórios ou ORM; um teste de
arquitetura verifica os imports. Erros de domínio chegam aqui já traduzidos em
``UserFacingError``; qualquer outro erro sobe como falha interna.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from typing import Any, TypeVar

from dash import callback_context
from pydantic import ValidationError

from lipidence_modular.application.context import AppContext
from lipidence_modular.application.contracts import AuthenticatedSession, UserOut
from lipidence_modular.application.errors import ErrorInfo, UserFacingError, user_facing
from lipidence_modular.application.experimental_contracts import (
    BaseSummary,
    FilterOptions,
    ImportKind,
    ImportPlan,
    ImportPreview,
    ImportReport,
    ManualReferenceIn,
    ManualSampleIn,
    SampleFilters,
    SampleList,
    StagedImport,
)

__all__ = ["Gateway", "UserFacingError"]

T = TypeVar("T")


class Gateway:
    def __init__(self, context: AppContext):
        self._context = context

    @property
    def base_path(self) -> str:
        return self._context.settings.dash_prefix

    # --- sessão ------------------------------------------------------------------------
    def session_from_token(self, token: str | None) -> AuthenticatedSession | None:
        return self._context.auth.resolve(token)

    def current_session(self) -> AuthenticatedSession | None:
        """Sessão do usuário que disparou o callback corrente."""
        cookies = callback_context.cookies or {}
        return self.session_from_token(cookies.get(self._context.settings.session_cookie_name))

    def _user(self) -> UserOut:
        session = self.current_session()
        if session is None:
            raise UserFacingError(ErrorInfo(401, "sessão expirada; entre novamente"))
        return session.user

    @staticmethod
    def _call(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            first = exc.errors()[0]
            where = ".".join(str(p) for p in first["loc"])
            raise UserFacingError(ErrorInfo(422, f"{where}: {first['msg']}")) from exc
        except Exception as exc:
            translated = user_facing(exc)
            if translated is None:
                raise
            raise translated from exc

    # --- base experimental -------------------------------------------------------------
    def summary(self) -> BaseSummary:
        return self._call(self._context.base.summary)

    def filter_options(self) -> FilterOptions:
        return self._call(self._context.base.filter_options)

    def list_samples(self, **filters: Any) -> SampleList:
        return self._call(lambda: self._context.base.list_samples(SampleFilters(**filters)))

    def parameters(self) -> list[dict[str, Any]]:
        vocabulary = self._context.imports.vocabulary
        return [{"name": spec.name, "label": spec.label, "units": list(spec.units)}
                for spec in vocabulary.parameters.values()]

    def stage_upload(self, contents: str, filename: str, kind: str,
                     study_id: str) -> StagedImport:
        """``contents`` no formato do ``dcc.Upload``: ``data:<tipo>;base64,<dados>``."""
        user = self._user()
        try:
            content = base64.b64decode(contents.split(",", 1)[1], validate=True)
        except (IndexError, binascii.Error) as exc:
            raise UserFacingError(ErrorInfo(422, "upload ilegível")) from exc
        return self._call(
            lambda: self._context.imports.stage(
                content=content, filename=filename, kind=ImportKind(kind),
                study_id=study_id or "", user=user,
            )
        )

    def preview_import(self, import_batch_id: str, plan: dict[str, Any]) -> ImportPreview:
        user = self._user()
        return self._call(
            lambda: self._context.imports.preview(import_batch_id, ImportPlan(**plan), user))

    def confirm_import(self, import_batch_id: str, plan: dict[str, Any]) -> ImportReport:
        user = self._user()
        return self._call(
            lambda: self._context.imports.confirm(import_batch_id, ImportPlan(**plan), user))

    def register_sample(self, **data: Any) -> str:
        user = self._user()
        return self._call(
            lambda: self._context.imports.register_sample(ManualSampleIn(**data), user))

    def register_reference(self, **data: Any) -> int:
        user = self._user()
        return self._call(
            lambda: self._context.imports.register_reference(ManualReferenceIn(**data), user))
