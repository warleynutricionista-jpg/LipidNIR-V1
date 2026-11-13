"""Erros de domínio compartilhados. Nada falha em silêncio (INV-7)."""


class LipidenceError(Exception):
    """Base de todos os erros do pacote."""


class ConfigurationError(LipidenceError):
    """Configuração ausente, inválida ou com opção sem implementação."""


class NotImplementedOptionError(ConfigurationError):
    """Opção pedida não tem implementação. Nunca cair em alternativa silenciosa."""


class IdentityError(LipidenceError):
    """Identidade de amostra ausente ou inválida (INV-1)."""


class IdentityConflictError(IdentityError):
    """Fontes diferentes informam identidades diferentes; exige confirmação explícita."""

    def __init__(self, field: str, candidates: dict[str, str]):
        self.field = field
        self.candidates = dict(candidates)
        detail = ", ".join(f"{src}={val!r}" for src, val in sorted(candidates.items()))
        super().__init__(f"CONFLITO DE IDENTIFICAÇÃO em '{field}': {detail}")


class StorageError(LipidenceError):
    """Falha no armazenamento de artefatos."""


class ArtifactIntegrityError(StorageError):
    """Conteúdo não confere com o hash registrado, ou tentativa de sobrescrever."""


class RegistryError(LipidenceError):
    """Manifesto inválido, id duplicado ou componente desconhecido."""
