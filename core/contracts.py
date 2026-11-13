"""Contratos do sistema.

O núcleo conhece apenas estes contratos, nunca as implementações (seção 6).

Infraestrutura: ``ArtifactStorage``, ``JobRunner``, ``Tracker``, ``AnalyticsStore``.
Ciência: ``Preprocessor``, ``BaseRegressor`` (e capacidades), ``Splitter``,
``DomainDetector``, ``IntervalCalibrator``, ``Attributor``.

Cada contrato de infraestrutura tem uma bateria de testes em ``tests/contracts/`` que toda
implementação, presente ou futura, precisa passar.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ----------------------------------------------------------------------------------------
# Infraestrutura
# ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ArtifactRef:
    """Referência imutável a um artefato armazenado."""

    key: str
    sha256: str
    size_bytes: int


class ArtifactStorage(ABC):
    """Armazenamento de arquivos brutos, retratos de dataset e bundles de modelo.

    Chaves são caminhos relativos com ``/``. Artefatos são imutáveis: gravar a mesma chave
    com o mesmo conteúdo é idempotente; com conteúdo diferente é erro.
    """

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> ArtifactRef: ...

    @abstractmethod
    def put_file(self, key: str, source: Path) -> ArtifactRef: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def download_to(self, key: str, destination: Path) -> Path: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def stat(self, key: str) -> ArtifactRef: ...

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]: ...


class JobState(enum.StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class JobInfo:
    job_id: str
    name: str
    state: JobState
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: Any = None
    error: str | None = None

    @property
    def done(self) -> bool:
        return self.state in (JobState.SUCCEEDED, JobState.FAILED)


class JobRunner(ABC):
    """Execução de tarefas demoradas (treino). A falha de um job nunca é engolida:
    fica em ``JobInfo.error`` com estado ``FAILED``."""

    @abstractmethod
    def submit(self, name: str, func: Callable[..., Any], /, **kwargs: Any) -> str: ...

    @abstractmethod
    def get(self, job_id: str) -> JobInfo: ...

    @abstractmethod
    def wait(self, job_id: str, timeout: float | None = None) -> JobInfo: ...

    @abstractmethod
    def shutdown(self) -> None: ...


class Tracker(ABC):
    """Registro de experimentos (seção 16). Implementações: ``NullTracker`` (Fase 3) e
    adapter MLflow (Fase 7)."""

    @abstractmethod
    def start_run(self, experiment_id: str, tags: Mapping[str, str]) -> str: ...

    @abstractmethod
    def log_params(self, run_id: str, params: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def log_metrics(self, run_id: str, metrics: Mapping[str, float]) -> None: ...

    @abstractmethod
    def log_artifact(self, run_id: str, path: Path, artifact_path: str | None = None) -> None: ...

    @abstractmethod
    def end_run(self, run_id: str, status: str) -> None: ...


class AnalyticsStore(ABC):
    """Consulta analítica sobre os retratos Parquet (DuckDB na V1)."""

    @abstractmethod
    def query(self, sql: str, tables: Mapping[str, Path]) -> list[dict[str, Any]]: ...


# ----------------------------------------------------------------------------------------
# Ciência
# ----------------------------------------------------------------------------------------


@runtime_checkable
class Preprocessor(Protocol):
    """Etapa de pré-processamento com a interface ``fit/transform`` do scikit-learn.

    ``learns_from_data`` declara se o ``fit`` aprende com os dados (ex.: MSC); o manifesto
    do método repete essa informação e um teste confere as duas (INV-3).
    """

    learns_from_data: bool

    def fit(self, X: Any, y: Any = None) -> Preprocessor: ...

    def transform(self, X: Any) -> Any: ...


class BaseRegressor(ABC):
    """Contrato mínimo de modelo (seção 11.1). ``predict`` devolve sempre uma matriz
    ``(n_amostras, n_targets)``, na ordem dos targets do ``fit``."""

    @abstractmethod
    def fit(self, X: Any, y: Any) -> BaseRegressor: ...

    @abstractmethod
    def predict(self, X: Any) -> Any: ...

    @abstractmethod
    def save(self, path: Path) -> None: ...

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> BaseRegressor: ...

    @abstractmethod
    def get_metadata(self) -> dict[str, Any]: ...


@runtime_checkable
class SupportsMultiOutput(Protocol):
    """Capacidade: saída múltipla nativa (um único estimador para vários targets)."""

    native_multi_output: bool


@runtime_checkable
class SupportsFeatureImportance(Protocol):
    """Capacidade: importância de variáveis própria do algoritmo (ressalva do INV-11)."""

    def feature_importances(self) -> Any: ...


@runtime_checkable
class DeepLearningModel(Protocol):
    """Capacidade: modelo treinado por épocas, com histórico de treino."""

    def training_history(self) -> list[dict[str, float]]: ...


class Splitter(ABC):
    """Estratégia de partição (seção 9.2). Devolve atribuição com ``split_hash``."""

    @abstractmethod
    def split(self, sample_ids: Sequence[str], groups: Sequence[str] | None, seed: int) -> Any: ...


class DomainState(enum.StrEnum):
    DENTRO = "DENTRO"
    LIMITROFE = "LIMITROFE"
    FORA = "FORA"


class DomainDetector(ABC):
    """Domínio de aplicação (seção 12), ajustado só com a calibração (INV-3)."""

    @abstractmethod
    def fit(self, X: Any) -> DomainDetector: ...

    @abstractmethod
    def assess(self, X: Any) -> list[Any]: ...


class IntervalCalibrator(ABC):
    """Intervalo de predição por target (seção 12)."""

    @abstractmethod
    def calibrate(self, residuals: Any) -> IntervalCalibrator: ...

    @abstractmethod
    def interval(self, y_pred: Any) -> tuple[Any, Any]: ...


@dataclass(frozen=True)
class AttributionMap:
    """Mapa de atribuição calculado por um método declarado sobre o modelo real (INV-14)."""

    method: str
    target: str
    axis: tuple[float, ...]
    values: tuple[float, ...]
    space: str  # "raw" (eixo original) | "preprocessed" (entrada do estimador)
    details: dict[str, Any] = field(default_factory=dict)


class AttributionUnavailableError(Exception):
    """O método não se aplica a este modelo. A interface mostra "indisponível";
    nunca se substitui por outro método (INV-14)."""


class Attributor(ABC):
    method: str

    @abstractmethod
    def supports(self, model_id: str) -> bool: ...

    @abstractmethod
    def attribute(self, bundle: Any, X: Any, y: Any, target: str) -> AttributionMap: ...
