"""The sidecar diagnosis preserves unknowns and its actual negative controls fail."""
import importlib.util
from pathlib import Path

from ioabench.v5.ai_generation.acquisition import program_proposal
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.v5.dynamic.gates import check_pair_dynamic
import pytest


def script():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/verify_next_structure_history.py"
    spec = importlib.util.spec_from_file_location("verify_next_structure_history", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gap_classification_does_not_convert_unknown_to_novelty():
    module = script()
    assert module.gap_category({"error_type": "KeyError", "error": "'brief'"}) == "HISTORICAL_WORLD_SCHEMA_MISSING_REQUIRED_FIELD"
    assert module.gap_category({"error_type": "ValueError", "error": "Unsupported required scenario profile: 'old'"}) == "HISTORICAL_REQUIRED_PROFILE_UNSUPPORTED"
    assert module.gap_category({"error_type": "RuntimeError"}) == "UNCLASSIFIED_REQUIRES_DIAGNOSIS"


def test_immutable_evidence_refuses_rewrite(tmp_path):
    module = script()
    target = tmp_path / "proof.json"
    module.write(target, {"status": "INDETERMINATE"})
    module.write(target, {"status": "INDETERMINATE"})
    with pytest.raises(ValueError, match="immutable"):
        module.write(target, {"status": "VERIFIED_NEW_FAMILY"})


def test_resume_rejects_a_different_source_before_running_any_policy(tmp_path, monkeypatch):
    module = script()
    module.write(tmp_path / "STRUCTURE_PROOFS.json", {"runtime_source_sha256": "recorded"})
    monkeypatch.setattr(module, "source_tree_hash", lambda root: "changed")
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **kw: pytest.fail("must not rerun"))
    with pytest.raises(AssertionError, match="recorded source"):
        module.resume_structure_proofs(tmp_path)


@pytest.mark.parametrize("suite", ["T321", "T331", "T352"])
def test_counterfactual_instrumentation_is_rejected_by_existing_gate(suite):
    module = script()
    spec = suite_spec(suite, typed=True)
    blueprint = program_proposal(spec, seed=6101910, difficulty="M", target=module.TARGETS[suite][-1])
    pair = spec.adapter.compile_pair(blueprint, seed=6101910)
    gate = check_pair_dynamic(*pair, scenario=module.negative_scenario(spec), scorer=spec.scorer,
        policies=spec.policies, expected=spec.expected, fine_arm_delta=spec.adapter.verify_arm_delta)
    assert not gate["passed"] and gate["failures"]
