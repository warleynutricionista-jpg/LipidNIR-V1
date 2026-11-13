"""Bateria do contrato ``JobRunner``. Toda implementação fornece a fixture ``runner``."""

from __future__ import annotations

import threading

import pytest

from lipidence_modular.core.contracts import JobState
from lipidence_modular.core.errors import LipidenceError


def _add(a, b):
    return a + b


def _boom():
    raise ValueError("falha proposital")


class JobRunnerContract:
    def test_success_carries_result(self, runner):
        info = runner.wait(runner.submit("soma", _add, a=2, b=3), timeout=10)
        assert info.state is JobState.SUCCEEDED
        assert info.result == 5
        assert info.done and info.error is None
        assert info.submitted_at <= info.started_at <= info.finished_at

    def test_failure_is_recorded_not_swallowed(self, runner):
        info = runner.wait(runner.submit("falha", _boom), timeout=10)
        assert info.state is JobState.FAILED
        assert "falha proposital" in info.error
        assert info.result is None

    def test_runner_survives_a_failed_job(self, runner):
        runner.wait(runner.submit("falha", _boom), timeout=10)
        assert runner.wait(runner.submit("soma", _add, a=1, b=1), timeout=10).result == 2

    def test_jobs_run_one_at_a_time_in_order(self, runner):
        order, gate = [], threading.Event()

        def first():
            gate.wait(5)
            order.append("first")

        def second():
            order.append("second")

        a = runner.submit("a", first)
        b = runner.submit("b", second)
        assert runner.get(b).state is JobState.QUEUED
        gate.set()
        runner.wait(a, 10)
        runner.wait(b, 10)
        assert order == ["first", "second"]

    def test_unknown_job_is_an_error(self, runner):
        with pytest.raises(LipidenceError):
            runner.get("nao-existe")

    def test_wait_timeout_returns_unfinished_state(self, runner):
        gate = threading.Event()
        job = runner.submit("lento", gate.wait, timeout=5)
        assert not runner.wait(job, timeout=0.05).done
        gate.set()
        assert runner.wait(job, timeout=10).done
