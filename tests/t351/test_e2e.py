from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t351.generation import T351Generator
from ioabench.suites.t351.scenario import T351ExposureController, T351Scenario
from ioabench.suites.t351.scoring import T351Scorer
def test_t351_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T351", T351Generator, T351Scenario, T351ExposureController, T351Scorer, "safety.verification")
