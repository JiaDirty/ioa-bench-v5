from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t353.generation import T353Generator
from ioabench.suites.t353.scenario import T353ExposureController, T353Scenario
from ioabench.suites.t353.scoring import T353Scorer
def test_t353_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T353", T353Generator, T353Scenario, T353ExposureController, T353Scorer, "router.compare")
