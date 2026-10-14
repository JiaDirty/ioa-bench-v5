from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t341.generation import T341Generator
from ioabench.suites.t341.scenario import T341ExposureController, T341Scenario
from ioabench.suites.t341.scoring import T341Scorer
def test_t341_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T341", T341Generator, T341Scenario, T341ExposureController, T341Scorer, "evidence.verification")
