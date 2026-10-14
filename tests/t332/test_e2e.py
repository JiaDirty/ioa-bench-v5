from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t332.generation import T332Generator
from ioabench.suites.t332.scenario import T332ExposureController, T332Scenario
from ioabench.suites.t332.scoring import T332Scorer


def test_t332_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T332", T332Generator, T332Scenario, T332ExposureController, T332Scorer, "structure.minimization.check")
