from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t322.generation import T322Generator
from ioabench.suites.t322.scenario import T322ExposureController, T322Scenario
from ioabench.suites.t322.scoring import T322Scorer

def test_t322_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T322", T322Generator, T322Scenario, T322ExposureController, T322Scorer, "interoperability.semantic.check")
