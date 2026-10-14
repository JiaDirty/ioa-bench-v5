from pathlib import Path
from ioabench.runtime.network_propagation import run_propagation_baseline
ROOT = Path(__file__).parents[2]
def test_t331_baselines_are_causal():
    assert run_propagation_baseline(ROOT,"T331","safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run_propagation_baseline(ROOT,"T331","naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run_propagation_baseline(ROOT,"T331","recovery")["score"]["outcome_class"] == "LATE_RECOVERY"
def test_t342_baselines_are_causal():
    assert run_propagation_baseline(ROOT,"T342","safe")["score"]["outcome_class"] == "EARLY_SAFE"
    assert run_propagation_baseline(ROOT,"T342","naive")["score"]["outcome_class"] == "FULL_FAILURE"
    assert run_propagation_baseline(ROOT,"T342","recovery")["score"]["outcome_class"] == "LATE_RECOVERY"
