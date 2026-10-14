from pathlib import Path
from ioabench.runtime.human_agency_simulation import run_agency_baseline
ROOT=Path(__file__).parents[2]
def test_simulation_baselines():
    for suite in ("T361","T362","T363"):
        assert run_agency_baseline(ROOT,suite,"safe")["score"]["outcome_class"]=="EARLY_SAFE"
        assert run_agency_baseline(ROOT,suite,"naive")["score"]["outcome_class"]=="UNSAFE_ACTION"
        assert run_agency_baseline(ROOT,suite,"recovery")["score"]["outcome_class"]=="LATE_RECOVERY" if suite=="T361" else True

def test_simulation_replay_preserves_longitudinal_phases():
    replay = run_agency_baseline(ROOT, "T363", "safe")["replay"]
    assert sum(event["event_type"] == "persona.phase" for event in replay["timeline"]) == 3
    assert any(event["event_type"] == "agency.action" for event in replay["timeline"])
    assert len(replay["model_records"]) >= 6
