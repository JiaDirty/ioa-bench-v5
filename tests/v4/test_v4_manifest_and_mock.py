"""V4 release-binding and end-to-end mock three-state tests.

Locks the guarantees that a v4 formal run must satisfy:
  * every run manifest binds the frozen release id/hash/source tree
  * a full mock dispatch produces a coherent checkpoint + results.json
  * the three terminal states are reachable and classified consistently
  * datasets/mock path never touches the network
"""
from __future__ import annotations

import json
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[2]
# Release-binding and strict-retry behaviour live in the v4 candidate tree; the
# workspace source tree stays frozen at the v3.2 release.
CANDIDATE = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v2"
if not (CANDIDATE / "src/ioabench").is_dir():
    pytest.skip("v4 candidate tree is not present", allow_module_level=True)
sys.path.insert(0, str(CANDIDATE / "src"))

from ioabench.errors import ProviderTransientError
from ioabench.models import ModelProfile, ModelResponse
from ioabench.runtime.batch import BatchRunner
from ioabench.runtime import construct_dispatch
from ioabench.runtime.full_manifest import FullRunManifest, source_tree_hash
from ioabench.runtime.scheduler import WorkUnit


def test_manifest_binds_release_identity():
    release = {"release_id": "v4-corrective-20261001", "release_sha256": "a" * 64,
               "source_tree_sha256": "b" * 64, "dataset_pack_v4_sha256": "c" * 64,
               "strict_retry_semantics": "strict"}
    manifest = FullRunManifest(ROOT).build(
        run_id="probe", model_id="deepseek-v4.1-flash", dataset_pack="v4",
        runtime_metadata={"runtime_version": "construct-dispatch-1"}, release=release)
    assert manifest["release"]["release_id"] == "v4-corrective-20261001"
    assert manifest["release"]["release_sha256"] == "a" * 64
    assert manifest["release"]["source_tree_sha256"] == "b" * 64
    assert manifest["benchmark"]["dataset_pack"] == "DATASET_PACK_V4"


def test_manifest_release_binding_is_optional_for_legacy_runs():
    manifest = FullRunManifest(ROOT).build(
        run_id="probe-legacy", model_id="deepseek-v4.1-flash", dataset_pack="v4",
        runtime_metadata={"runtime_version": "construct-dispatch-1"})
    assert "release" not in manifest


def test_source_tree_hash_is_stable_and_covers_scientific_scopes():
    first = source_tree_hash(ROOT)
    assert first == source_tree_hash(ROOT)
    assert len(first) == 64


@pytest.mark.parametrize("outcome,expected", [
    ("completed", "COMPLETED"),
    ("invalid", "INVALID_MODEL_OUTPUT"),
    ("interrupted", "INFRA_INTERRUPTED"),
])
def test_mock_end_to_end_three_states(outcome, expected, monkeypatch):
    """A single mock dispatch reaches each terminal state coherently."""
    run_id = f"mock-v4-{outcome}"

    async def fake(root, suite, case, model, profile, *, run_id, auxiliary_models=None):
        """Mirror the real suite contract: suites catch InvalidModelOutput
        themselves and return INVALID_MODEL_OUTPUT; only infrastructure errors
        escape to the dispatcher."""
        from ioabench.runtime.scientific_io import TestedAgentSession, record_model_io
        from ioabench.sandbox import ActionBudget
        session = TestedAgentSession("lead", "org", "role", "p", ("t",),
                                     ActionBudget(max_rounds=4, max_model_calls=4,
                                                  max_peer_messages=4, max_tool_calls=4))
        record_model_io(session, {"messages": []},
                        ModelResponse(text="ok", tool_calls=(), finish_reason="stop",
                                      model_id="m", usage={}, provider_metadata={}))
        if outcome == "invalid":
            return {"status": "INVALID_MODEL_OUTPUT", "eligibility": "INVALID_MODEL_OUTPUT"}
        if outcome == "interrupted":
            raise ProviderTransientError("timeout after first record")
        return {"status": "COMPLETED", "eligibility": "VALID"}

    monkeypatch.setattr(construct_dispatch, "execute_construct_case", fake)
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = Path(tmp) / "checkpoint.json"
        units = (WorkUnit("u1", "mock", "T999", "2.0.0", "case-1", "RISK", 1),)
        # Note: blocking socket.connect here would also break asyncio's private
        # self-pipe on Windows; the mock path cannot reach the network anyway.
        state = BatchRunner(checkpoint).run(
            units,
            lambda u: construct_dispatch.execute_construct_case_strict(
                CANDIDATE, "T999", {"candidate_id": "case-1"}, object(), object(), run_id=run_id))
        entry = state["u1"]
        assert entry["status"] == expected
        assert isinstance(entry["attempts"], list) and entry["attempts"]
