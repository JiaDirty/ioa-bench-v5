from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t362.generation import T362Generator
from ioabench.suites.t362.scenario import T362ExposureController, T362Scenario
from ioabench.suites.t362.scoring import T362Scorer
def test_t362_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T362", T362Generator, T362Scenario, T362ExposureController, T362Scorer, "discussion.message")
