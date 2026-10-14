"""Executor-signature contract tests (T341-T343 pilot incident regression).

The pilot's execute_with_retry passes auxiliary_models only to executors that
accept it.  The 2026-09-29 incident: an unconditional kwarg broke every
non-simulation suite with a TypeError masked as PROVIDER_FAILURE.  These tests
pin the executor-signature contract so the mismatch fails loudly in CI.
"""
from __future__ import annotations

import importlib
import inspect

from ioabench.runtime.construct_dispatch import RUNNERS, SIMULATION_SUITES


def _executor(suite: str):
    _, _, module_name, executor_name = RUNNERS[suite]
    return getattr(importlib.import_module(module_name), executor_name)


def test_non_simulation_executors_reject_auxiliary_models():
    for suite in sorted(set(RUNNERS) - SIMULATION_SUITES):
        params = inspect.signature(_executor(suite)).parameters
        assert "auxiliary_models" not in params, (
            f"{suite} executor must not accept auxiliary_models (non-simulation suites are "
            "invoked without the binding; accepting it silently diverges from the formal dispatcher)")


def test_simulation_executors_accept_auxiliary_models():
    for suite in sorted(SIMULATION_SUITES):
        params = inspect.signature(_executor(suite)).parameters
        assert "auxiliary_models" in params, (
            f"{suite} executor must accept auxiliary_models for the synthetic-human binding")


def test_all_runners_share_common_signature_prefix():
    for suite in sorted(RUNNERS):
        params = list(inspect.signature(_executor(suite)).parameters)
        assert params[:4] == ["root", "case", "model", "profile"], (
            f"{suite} executor signature drift: {params[:4]}")
        assert "run_id" in params
