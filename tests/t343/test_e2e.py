from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t343.generation import T343Generator
from ioabench.suites.t343.scenario import T343ExposureController, T343Scenario
from ioabench.suites.t343.scoring import T343Scorer
def test_t343_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T343", T343Generator, T343Scenario, T343ExposureController, T343Scorer, "norm.correction")
