from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t313.generation import T313Generator
from ioabench.suites.t313.scenario import T313ExposureController, T313Scenario
from ioabench.suites.t313.scoring import T313Scorer

def test_t313_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T313", T313Generator, T313Scenario, T313ExposureController, T313Scorer, "delegation.boundary.check")
