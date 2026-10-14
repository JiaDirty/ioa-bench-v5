from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t333.generation import T333Generator
from ioabench.suites.t333.scenario import T333ExposureController, T333Scenario
from ioabench.suites.t333.scoring import T333Scorer


def test_t333_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T333", T333Generator, T333Scenario, T333ExposureController, T333Scorer, "inference.result")
