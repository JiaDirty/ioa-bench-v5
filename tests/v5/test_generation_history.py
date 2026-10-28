from copy import deepcopy
import json

import pytest

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.history import attach_probe, behavioral_signature, build_index, classify, discover_sources, verify_sources
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.dynamic import t321_slice, t331_slice
from ioabench.v5.dynamic.runner import run_dynamic_case


def _pair():
    return next(iter(t331_slice.generate(seed=17, families=1)))


def _write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")
    return target


def test_rejected_history_is_indexed_without_exporting_oracle(tmp_path):
    pair = _pair()
    _write(tmp_path, "artifacts/v5/data_factory/trials/rejected/candidate-01/PAIR.json", [case.as_dict() for case in pair])
    _write(tmp_path, "artifacts/v5/data_factory/trials/rejected/candidate-01/RESULT.json", {"status": "REJECTED"})
    index = build_index(tmp_path)
    assert index["summary"]["unique_cases"] == 2
    assert index["summary"]["occurrence_statuses"] == {"REJECTED": 2}
    assert "oracle" not in json.dumps(index)
    candidate = deepcopy(pair[0].as_dict())
    candidate["case_id"] = "new-label"
    evidence = classify(candidate, index, scenario=t331_slice.T331DynamicScenario())
    assert evidence["status"] == "EXACT_DUPLICATE" and not evidence["new_family"]
    verify_sources(tmp_path, index)


def test_source_mutation_missing_file_and_path_escape_fail_closed(tmp_path):
    path = _write(tmp_path, "data/v5/test/cases.json", _pair()[0].as_dict())
    index = build_index(tmp_path, sources=[path])
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="changed or missing"):
        verify_sources(tmp_path, index)
    path.unlink()
    with pytest.raises(ValueError, match="changed or missing"):
        verify_sources(tmp_path, index)
    index["source_sha256"] = {"../outside.json": "x"}
    with pytest.raises(ValueError, match="changed or missing"):
        verify_sources(tmp_path, index)


def test_static_difference_is_only_candidate_until_fixed_behavior_probes(tmp_path):
    base, _ = _pair()
    path = _write(tmp_path, "data/v5/candidate/cases.json", base.as_dict())
    index = build_index(tmp_path, sources=[path])
    candidate = deepcopy(base.as_dict())
    node = next(key for key, targets in candidate["world"]["downstream"].items() if len(targets) > 1)
    candidate["world"]["downstream"][node] = candidate["world"]["downstream"][node][:1]
    evidence = classify(candidate, index, scenario=t331_slice.T331DynamicScenario())
    assert evidence["status"] == "CANDIDATE_NEW_FAMILY" and not evidence["new_family"]
    def run(case, label):
        return {name: run_dynamic_case(tmp_path / "replay", case, t331_slice, policy,
                    ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY"),
                    run_id=label + name, parameters={"temperature": 0.0})
                for name, policy in t331_slice.policies().items() if name in {"witness", "naive"}}
    probe = attach_probe(index, base, run(base, "base"), policy_contract="t331-fixed-reference/1")
    candidate_case = case_from_dict(candidate, allow_dynamic=True)
    changed = behavioral_signature(candidate_case, run(candidate_case, "changed"), policy_contract="t331-fixed-reference/1")
    evidence = classify(candidate, index, scenario=t331_slice.T331DynamicScenario(), behavioral_probe_signature=changed)
    assert evidence["status"] == "VERIFIED_NEW_FAMILY" and evidence["new_family"]
    changed["policy_contract"] = "other-policy"
    assert classify(candidate, index, scenario=t331_slice.T331DynamicScenario(), behavioral_probe_signature=changed)["status"] == "INDETERMINATE"
    changed["policy_contract"] = probe["policy_contract"]
    changed["behavior"] = probe["behavior"]
    assert classify(candidate, index, scenario=t331_slice.T331DynamicScenario(), behavioral_probe_signature=changed)["status"] == "INDETERMINATE"
    with pytest.raises(ValueError, match="case-bound complete"):
        behavioral_signature(base, {"witness": {}, "naive": {}}, policy_contract="x/1")


def test_malformed_source_and_empty_reference_never_prove_novelty(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text("not json", encoding="utf-8")
    index = build_index(tmp_path, sources=[path])
    result = classify(_pair()[0], index, scenario=t331_slice.T331DynamicScenario())
    assert result["status"] == "INDETERMINATE" and not result["new_family"]
    assert index["findings"][0]["code"] == "SOURCE_NOT_INDEXABLE"
    empty = build_index(tmp_path, sources=[])
    assert classify(_pair()[0], empty, scenario=t331_slice.T331DynamicScenario())["status"] == "INDETERMINATE"


def test_discovery_excludes_fixture_copies_but_keeps_rejected_and_dynamic(tmp_path):
    _write(tmp_path, "data/v5/dynamic_experimental/t331/cases.json", _pair()[0].as_dict())
    _write(tmp_path, "artifacts/v5/trials/run/candidate-01/PAIR.json", [])
    _write(tmp_path, "artifacts/v5/trials/run/rejected.jsonl", [])
    _write(tmp_path, "artifacts/v5/review/pytest-focused/test_foo/PAIR.json", [])
    _write(tmp_path, "artifacts/v5/review/source/data/v5/cases.json", [])
    assert len(discover_sources(tmp_path)) == 3


def test_discovery_includes_case_schema_inside_arbitrary_named_evidence(tmp_path):
    case = t331_slice.generate(19, families=1)[0][0]
    path = _write(tmp_path, "artifacts/v5/review/UNUSUAL_EVIDENCE.json", {"sample": case.as_dict()})
    assert path in discover_sources(tmp_path)
    index = build_index(tmp_path)
    assert index["summary"]["unique_cases"] == 1


def test_new_source_invalidates_automatic_historical_inventory(tmp_path):
    _write(tmp_path, "data/v5/first/cases.json", _pair()[0].as_dict())
    index = build_index(tmp_path)
    verify_sources(tmp_path, index)
    _write(tmp_path, "data/v5/later/cases.json", _pair()[0].as_dict())
    with pytest.raises(ValueError, match="inventory changed"):
        verify_sources(tmp_path, index)


def test_runtime_projection_code_change_requires_a_new_index(tmp_path):
    path = _write(tmp_path, "data/v5/cases.json", _pair()[0].as_dict())
    index = build_index(tmp_path, sources=[path])
    source = tmp_path / "src" / "projection.py"
    source.parent.mkdir(parents=True)
    source.write_text("changed = True\n", encoding="utf-8")
    with pytest.raises(ValueError, match="runtime projection source changed"):
        verify_sources(tmp_path, index)


def test_repeated_source_keeps_occurrences_and_suites_are_never_merged(tmp_path):
    base, _ = _pair()
    one = _write(tmp_path, "data/v5/a/cases.json", base.as_dict())
    two = _write(tmp_path, "data/v5/b/cases.json", base.as_dict())
    index = build_index(tmp_path, sources=[one, two])
    assert index["summary"]["unique_cases"] == 1 and index["summary"]["occurrences"] == 2
    candidate, _ = next(iter(t321_slice.generate(seed=17, families=1)))
    assert classify(candidate, index, scenario=t321_slice.T321DynamicAScenario())["status"] == "INDETERMINATE"
