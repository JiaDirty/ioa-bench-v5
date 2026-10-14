from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t352.generation import T352Generator
from ioabench.suites.t352.scenario import T352ExposureController, T352Scenario
from ioabench.suites.t352.scoring import T352Scorer
def test_t352_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T352", T352Generator, T352Scenario, T352ExposureController, T352Scorer, "reputation.compare")
