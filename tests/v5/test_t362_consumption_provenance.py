"""The compiler must persist real consumed mappings without changing old worlds."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.audit_facts import compute_audit_facts
from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler
from ioabench.v5.ai_generation.t362_compiler import T362DynaCompiler
from ioabench.v5.core.case import resolve_pointer

FIXTURES = json.loads((Path(__file__).resolve().parents[1] / "fixtures/v5/t362_compiler_1_1_worlds.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=[Path(row["source_candidate"]).name for row in FIXTURES])
def test_consumption_paths_are_real_and_legacy_worlds_oracles_identical(fixture):
    compiler = T362DynaCompiler()
    pair = compiler.compile_pair(fixture["blueprint"], seed=fixture["seed"])
    for case in pair:
        assert canonical_sha256(case.world) == fixture["expected_world_sha256"][case.arm]
        assert canonical_sha256(case.oracle) == fixture["expected_oracle_sha256"][case.arm]
        mappings = case.provenance.get("proposal_to_runtime_mapping")
        assert mappings
        for row in mappings:
            assert row["status"] == "MAPPED"
            resolve_pointer(fixture["blueprint"], row["blueprint_path"])
            resolve_pointer(case.world, row["runtime_path"].removeprefix("/world"))
    facts = compute_audit_facts([case.as_dict() for case in pair], [], [], {"runs": []})
    assert facts["metadata_only_declaration_paths"] == []
    assert "/suite_payload/business_binding" in facts["structural_basis_paths"]
    assert "/suite_payload/evidence_flow" in facts["structural_basis_paths"]


def test_plain_bounded_legacy_path_retains_identical_bytes():
    compiler = T362DynaCompiler()
    blueprint = deepcopy(FIXTURES[0]["blueprint"])
    for key in ["evidence_flow", "evidence_release", "source_release", "relay_before_digest", "business_binding"]:
        blueprint["suite_payload"].pop(key, None)
    expected = BoundedWorldCompiler("T362-DYNA").compile_pair(blueprint, seed=31)
    actual = compiler.compile_pair(blueprint, seed=31)
    assert [case.as_dict() for case in actual] == [case.as_dict() for case in expected]
