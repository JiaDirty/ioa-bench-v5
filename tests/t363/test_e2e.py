from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t363.generation import T363Generator
from ioabench.suites.t363.scenario import T363ExposureController, T363Scenario
from ioabench.suites.t363.scoring import T363Scorer
def test_t363_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T363", T363Generator, T363Scenario, T363ExposureController, T363Scorer, "agency.challenge")
