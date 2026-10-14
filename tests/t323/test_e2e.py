from pathlib import Path
from tests.m5_support import run_mini_e2e
from ioabench.suites.t323.generation import T323Generator
from ioabench.suites.t323.scenario import T323ExposureController, T323Scenario
from ioabench.suites.t323.scoring import T323Scorer

def test_t323_e2e() -> None:
    run_mini_e2e(Path(__file__).parents[2], "T323", T323Generator, T323Scenario, T323ExposureController, T323Scorer, "accountability.provenance.check")
