from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t342.generation import T342Generator
from ioabench.suites.t342.scenario import T342ExposureController, T342Scenario
from ioabench.suites.t342.scoring import T342Scorer
def test_t342_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T342", T342Generator, T342Scenario, T342ExposureController, T342Scorer, "rumor.verify")
