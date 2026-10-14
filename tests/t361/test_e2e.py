from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t361.generation import T361Generator
from ioabench.suites.t361.scenario import T361ExposureController, T361Scenario
from ioabench.suites.t361.scoring import T361Scorer
def test_t361_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T361", T361Generator, T361Scenario, T361ExposureController, T361Scorer, "persona.verification")
