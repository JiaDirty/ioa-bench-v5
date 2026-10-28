from copy import deepcopy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("round01_readiness", ROOT / "scripts/v5/verify_round01_readiness.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_readiness_requires_executed_consumer_and_negative_evidence():
    row = {"registered": True, "status": "SUPPORTED", "structural_acquisition": "SUPPORTED",
        "reference_gate": "PASS", "execution_fidelity": "PASS",
        "unsupported_field_control": {"status": "REJECTED"},
        "factor_examples": [{"status": "SUPPORTED", "reference_gate": "PASS", "execution_fidelity": "PASS"}]}
    assert module.typed_ready(row)
    for path in ("reference_gate", "execution_fidelity"):
        broken = deepcopy(row)
        broken[path] = "NOT_RUN"
        assert not module.typed_ready(broken)
        broken = deepcopy(row)
        broken["factor_examples"][0][path] = "NOT_RUN"
        assert not module.typed_ready(broken)
    row["unsupported_field_control"]["status"] = "FAIL"
    assert not module.typed_ready(row)
    row["unsupported_field_control"]["status"] = "REJECTED"
    row["factor_examples"][0]["status"] = "UNSUPPORTED"
    assert not module.typed_ready(row)


def test_staged_mock_preserves_blueprint_and_removed_intervention_is_rejected():
    from ioabench.v5.ai_generation.acquisition import program_proposal
    spec = module.suite_spec("T331", typed=True)
    blueprint = program_proposal(spec, seed=81, difficulty="M")
    control, risk = spec.adapter.compile_pair(blueprint, seed=81)
    staged = module.staged_mock(spec, blueprint, 81)
    assert staged["status"] == "PASS_MOCK_ONLY" and staged["stage_count"] == 4
    assert staged["provider_calls"] == 0
    rejected = module.no_intervention_negative(spec,
        {"pair": [control.as_dict(), risk.as_dict()], "blueprint": blueprint}, 81)
    assert rejected["status"] == "REJECTED" and rejected["stage"] == "ARM_DELTA"
