"""Precedência e conflito de metadados (seções 8.3 e 8.4).

Cada valor carrega a sua origem. O sistema nunca escolhe sozinho entre duas identidades
diferentes: levanta ``IdentityConflictError`` até haver confirmação explícita.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from lipidence_modular.core.errors import IdentityConflictError, IdentityError
from lipidence_modular.data.identity.normalization import normalize_sample_id


class FieldOrigin(enum.StrEnum):
    FILE = "FILE"
    AUTO_DETECTED = "AUTO_DETECTED"
    USER_CONFIRMED = "USER_CONFIRMED"
    USER_ENTERED = "USER_ENTERED"


UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ResolvedField:
    value: str
    origin: FieldOrigin
    raw: str


def resolve_sample_id(
    *,
    from_file: object = None,
    auto_detected: object = None,
    user_value: object = None,
    conflict_confirmed: bool = False,
) -> ResolvedField:
    """Resolve o ``sample_id`` final de um item.

    - ``from_file``: valor de uma coluna/campo do arquivo.
    - ``auto_detected``: sugestão (ex.: nome do arquivo). Só vale se confirmada, isto é,
      se ``user_value`` repetir o mesmo valor; sozinha, nunca é identidade definitiva.
    - ``user_value``: valor digitado ou confirmado pelo usuário.
    - ``conflict_confirmed``: o usuário viu o conflito e confirmou o próprio valor.
    """

    def norm(value: object):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return normalize_sample_id(value)

    file_id, auto_id, user_id = norm(from_file), norm(auto_detected), norm(user_value)

    if user_id is not None:
        confirmed = ResolvedField(
            user_id.sample_id, FieldOrigin.USER_CONFIRMED, user_id.sample_id_raw
        )
        if file_id is not None and file_id.sample_id != user_id.sample_id:
            if not conflict_confirmed:
                raise IdentityConflictError(
                    "sample_id",
                    {
                        FieldOrigin.FILE.value: file_id.sample_id,
                        FieldOrigin.USER_ENTERED.value: user_id.sample_id,
                    },
                )
            return confirmed
        if file_id is not None or (auto_id is not None and auto_id.sample_id == user_id.sample_id):
            return confirmed
        return ResolvedField(user_id.sample_id, FieldOrigin.USER_ENTERED, user_id.sample_id_raw)

    if file_id is not None:
        return ResolvedField(file_id.sample_id, FieldOrigin.FILE, file_id.sample_id_raw)

    if auto_id is not None:
        raise IdentityError(
            f"sample_id sugerido ({auto_id.sample_id!r}, {FieldOrigin.AUTO_DETECTED.value}) "
            "precisa de confirmação do usuário"
        )
    raise IdentityError("sample_id ausente")


def resolve_optional(value: object, origin: FieldOrigin) -> ResolvedField:
    """Campo opcional ausente segue como ``UNKNOWN``; nunca se inventa valor."""
    if value is None or (isinstance(value, float) and value != value) or not str(value).strip():
        return ResolvedField(UNKNOWN, origin, "")
    text = str(value).strip()
    return ResolvedField(text, origin, str(value))
