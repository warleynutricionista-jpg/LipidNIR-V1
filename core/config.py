"""Configuração da aplicação, lida do ambiente. Sem valor padrão silencioso para o que
define onde os dados vivem: banco e diretório de artefatos são obrigatórios."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from lipidence_modular.core.errors import ConfigurationError

ENVIRONMENTS = ("development", "test", "production")


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_dir: Path
    environment: str = "development"
    session_ttl_minutes: int = 480
    session_cookie_name: str = "lm_session"
    csrf_cookie_name: str = "_csrf_token"  # nome lido pelo renderer do Dash
    csrf_header_name: str = "X-CSRFToken"
    dash_prefix: str = "/app/"

    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env

    def required(name: str) -> str:
        value = env.get(name, "").strip()
        if not value:
            raise ConfigurationError(f"variável de ambiente obrigatória ausente: {name}")
        return value

    environment = env.get("LIPIDENCE_ENV", "development").strip()
    if environment not in ENVIRONMENTS:
        raise ConfigurationError(
            f"LIPIDENCE_ENV={environment!r} inválido; valores aceitos: {', '.join(ENVIRONMENTS)}"
        )
    ttl_raw = env.get("LIPIDENCE_SESSION_TTL_MINUTES", "480").strip()
    try:
        ttl = int(ttl_raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"LIPIDENCE_SESSION_TTL_MINUTES={ttl_raw!r} não é inteiro"
        ) from exc
    if ttl <= 0:
        raise ConfigurationError("LIPIDENCE_SESSION_TTL_MINUTES deve ser positivo")
    return Settings(
        database_url=required("LIPIDENCE_DATABASE_URL"),
        storage_dir=Path(required("LIPIDENCE_STORAGE_DIR")).expanduser(),
        environment=environment,
        session_ttl_minutes=ttl,
    )
