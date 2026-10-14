from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t321.generation import T321Generator
from ioabench.suites.t321.scenario import T321ExposureController, T321Scenario
from ioabench.suites.t321.scoring import T321Scorer

def test_t321_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T321", T321Generator, T321Scenario, T321ExposureController, T321Scorer, "negotiation.verify")
