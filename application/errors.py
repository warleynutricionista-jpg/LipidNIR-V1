"""Tradução única de erros de domínio para a API, a CLI e a interface.

Nenhuma camada de entrega decide sozinha o que é erro do usuário: todas usam
``describe_error``. Exceção não reconhecida não é tratada aqui e sobe como erro interno.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lipidence_modular.application.auth_service import (
    InvalidCredentialsError,
    PermissionDeniedError,
    UserAlreadyExistsError,
)
from lipidence_modular.application.import_service import (
    DuplicateImportError,
    ImportNotFoundError,
    ImportStateError,
)
from lipidence_modular.core.errors import IdentityConflictError, LipidenceError
from lipidence_modular.data.ingestion.spectra import PlanError


@dataclass(frozen=True)
class ErrorInfo:
    status_code: int
    message: str
    extra: dict = field(default_factory=dict)


def describe_error(exc: Exception) -> ErrorInfo | None:
    if isinstance(exc, IdentityConflictError):
        return ErrorInfo(409, str(exc), {"conflict": {"field": exc.field,
                                                      "candidates": exc.candidates}})
    if isinstance(exc, DuplicateImportError):
        return ErrorInfo(409, str(exc), {"duplicate_of": exc.existing_batch_id})
    if isinstance(exc, ImportStateError | UserAlreadyExistsError):
        return ErrorInfo(409, str(exc))
    if isinstance(exc, ImportNotFoundError):
        return ErrorInfo(404, str(exc))
    if isinstance(exc, PermissionDeniedError):
        return ErrorInfo(403, str(exc))
    if isinstance(exc, InvalidCredentialsError):
        return ErrorInfo(401, str(exc))
    if isinstance(exc, PlanError | LipidenceError):
        return ErrorInfo(422, str(exc))
    return None


class UserFacingError(Exception):
    """Erro já traduzido, para camadas que não conhecem o domínio (interface)."""

    def __init__(self, info: ErrorInfo):
        self.info = info
        super().__init__(info.message)


def user_facing(exc: Exception) -> UserFacingError | None:
    info = describe_error(exc)
    return UserFacingError(info) if info else None
