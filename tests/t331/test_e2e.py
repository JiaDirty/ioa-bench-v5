from pathlib import Path

from tests.m5_support import run_mini_e2e
from ioabench.suites.t331.generation import T331Generator
from ioabench.suites.t331.scenario import T331ExposureController, T331Scenario
from ioabench.suites.t331.scoring import T331Scorer


def test_t331_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T331", T331Generator, T331Scenario, T331ExposureController, T331Scorer, "cascade.observed")
