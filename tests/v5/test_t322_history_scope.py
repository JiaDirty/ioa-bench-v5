from copy import deepcopy

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.history import HISTORY_VERSION
from ioabench.v5.ai_generation.quality import QUALITY_VERSION
from ioabench.v5.ai_generation.t322_history import (
    QUARANTINE, common_field_fingerprint, compare_common_fields, version_scoped_index,
)
from ioabench.v5.dynamic import t322_slice
from ioabench.v5.suites import t322


def _index():
    return {"index_version": HISTORY_VERSION, "feature_version": QUALITY_VERSION,
            "projection_source_sha256": "runtime", "source_sha256": {"cases.jsonl": "bound"},
            "discovered_sources": ["cases.jsonl"], "scope": {"archives": "NOT_SCANNED"},
            "records": [{"case_sha256": "legacy", "features": {"suite_id": "T322", "runtime_verified": False},
                         "occurrences": [{"source": "cases.jsonl", "line": 1}]},
                        {"case_sha256": "current", "features": {"suite_id": "T322-DYNA", "runtime_verified": True},
                         "occurrences": []}],
            "findings": [{"suite_id": "T322", "code": "RUNTIME_PROJECTION_UNAVAILABLE"},
                         {"suite_id": "T362", "code": "OTHER"}, {"code": "SOURCE_NOT_INDEXABLE"}],
            "summary": {"unique_cases": 2}}


def test_scoped_history_preserves_bindings_and_never_claims_global_uniqueness():
    original = _index()
    before = canonical_sha256(original)
    scoped, report = version_scoped_index(original)
    assert canonical_sha256(original) == before
    assert scoped["source_sha256"] == original["source_sha256"]
    assert scoped["discovered_sources"] == original["discovered_sources"]
    assert scoped["scope"]["archives"] == "NOT_SCANNED"
    assert [row["case_sha256"] for row in scoped["records"]] == ["current"]
    assert report["excluded_cases"][0]["case_sha256"] == "legacy"
    assert report["full_history_index_sha256"] == before
    assert report["required_pool_status"] == QUARANTINE
    assert not report["global_novelty_proven"] and not report["dev_accepted_allowed"]
    assert scoped["findings"] == original["findings"][1:]


def test_uninspected_contract_or_wrong_feature_version_is_rejected():
    with pytest.raises(ValueError, match="only the inspected"):
        version_scoped_index(_index(), target_version="5.1.0")
    changed = _index()
    changed["feature_version"] = "old"
    with pytest.raises(ValueError, match="rebuild"):
        version_scoped_index(changed)


def test_public_cross_version_primary_match_rejects_despite_renaming_and_oracle_change():
    current = t322.generate(seed=21, families=1)[0][0].as_dict()
    primary = deepcopy(current["world"]["instructions"][0])
    legacy = deepcopy(current)
    legacy["world"] = {**primary, "org": "old", "runbook": "observed historical text"}
    legacy["oracle"] = {"secret": "never included in public fingerprint"}
    assert common_field_fingerprint(current)["projection_sha256"] == common_field_fingerprint(legacy)["projection_sha256"]
    assert "secret" not in str(common_field_fingerprint(legacy))
    report = compare_common_fields(current, [legacy])
    assert report["status"] == "REJECTED_COMMON_FIELD_DUPLICATE"
    legacy["world"]["gateway"]["status_code"] = "UNSEEN_PUBLIC_STATE"
    report = compare_common_fields(current, [legacy])
    assert report["status"] == "NO_OBVIOUS_COMMON_FIELD_DUPLICATE"
    assert not report["global_novelty_proven"] and report["required_pool_status"] == QUARANTINE


def test_dynamic_transition_is_not_inferred_to_equal_static_record():
    static = t322.generate(seed=21, families=1)[0][0]
    dynamic = t322_slice.generate(seed=21, families=1)[0][0]
    assert common_field_fingerprint(static)["projection_kind"] != common_field_fingerprint(dynamic)["projection_kind"]
    assert not compare_common_fields(dynamic, [static])["matching_cases"]
    assert compare_common_fields(dynamic, [dynamic])["status"] == "REJECTED_COMMON_FIELD_DUPLICATE"
    raw = dynamic.as_dict()
    raw["world"]["native_transition"]["oracle"] = "hidden evaluator data"
    assert "hidden evaluator data" not in str(common_field_fingerprint(raw))


def test_missing_legacy_facts_are_reported_and_never_imputed():
    candidate = t322.generate(seed=21, families=1)[0][0].as_dict()
    broken = deepcopy(candidate)
    broken["world"] = {"gateway": {}}
    before = canonical_sha256(broken)
    report = compare_common_fields(candidate, [broken])
    assert len(report["incomparable_cases"]) == 1
    assert canonical_sha256(broken) == before
    assert not report["global_novelty_proven"]
