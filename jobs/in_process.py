"""``JobRunner`` em processo: uma fila, um worker (seção 5.3).

Suficiente enquanto o treino dura pouco e há um usuário treinando por vez. O estado dos
jobs vive na memória do processo; o registro durável do experimento é responsabilidade do
serviço que submete o job.
"""

from __future__ import annotations

import queue
import threading
import traceback
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from lipidence_modular.core.contracts import JobInfo, JobRunner, JobState
from lipidence_modular.core.errors import LipidenceError


def _now() -> datetime:
    return datetime.now(UTC)


class UnknownJobError(LipidenceError):
    pass


class InProcessJobRunner(JobRunner):
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, Callable[..., Any], dict[str, Any]] | None] = (
            queue.Queue()
        )
        self._jobs: dict[str, JobInfo] = {}
        self._events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._closed = False
        self._worker = threading.Thread(target=self._run, name="lm-job-worker", daemon=True)
        self._worker.start()

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            self._jobs[job_id] = replace(self._jobs[job_id], **changes)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            job_id, func, kwargs = item
            self._update(job_id, state=JobState.RUNNING, started_at=_now())
            try:
                result = func(**kwargs)
            except Exception:
                self._update(
                    job_id,
                    state=JobState.FAILED,
                    finished_at=_now(),
                    error=traceback.format_exc(),
                )
            else:
                self._update(
                    job_id, state=JobState.SUCCEEDED, finished_at=_now(), result=result
                )
            finally:
                self._events[job_id].set()

    def submit(self, name: str, func: Callable[..., Any], /, **kwargs: Any) -> str:
        if self._closed:
            raise LipidenceError("JobRunner encerrado; não aceita novos jobs")
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = JobInfo(
                job_id=job_id, name=name, state=JobState.QUEUED, submitted_at=_now()
            )
            self._events[job_id] = threading.Event()
        self._queue.put((job_id, func, kwargs))
        return job_id

    def get(self, job_id: str) -> JobInfo:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError:
                raise UnknownJobError(f"job desconhecido: {job_id}") from None

    def wait(self, job_id: str, timeout: float | None = None) -> JobInfo:
        self.get(job_id)
        self._events[job_id].wait(timeout)
        return self.get(job_id)

    def shutdown(self) -> None:
        if not self._closed:
            self._closed = True
            self._queue.put(None)
            self._worker.join(timeout=30)
