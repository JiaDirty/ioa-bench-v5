"""The authored pack must execute and replay with its declared scaffolding."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ioabench.models import ModelProfile
from ioabench.hashing import canonical_sha256
from ioabench.v5 import evaluation, replay
from ioabench.v5.core.engine import run_episode
from ioabench.v5.scenario_profiles import PROFILE_ID, scenario_for
from ioabench.v5.suites import load

PACK = Path(__file__).resolve().parents[2] / "artifacts/v5/manual_18/20261013-authored-scientific-r3"
REFERENCE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")


def test_authored_all18_batch_matches_original_profile_and_replays(tmp_path):
    spec = importlib.util.spec_from_file_location("original_profile", PACK / "execution_profile.py")
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    cases = evaluation.read_cases(PACK / "cases.jsonl")
    evaluation.run_batch(tmp_path, PACK / "cases.jsonl", run_id="authored", profile=REFERENCE,
                         reference_policy="witness")
    rows = evaluation.read_results(tmp_path / "artifacts/v5/evaluations/authored")
    assert len(rows) == 36
    for case, row in zip(cases, rows):
        module = load(case.suite_id)
        auxiliary = module.reference_auxiliary() if hasattr(module, "reference_auxiliary") else None
        trace = asyncio.run(run_episode(case, original.scenario_for(case), module.policies()["witness"],
                                        REFERENCE, parameters={}, auxiliary=auxiliary))
        assert row["status"] == trace.status == "COMPLETED"
        def without_elapsed(records):
            return [{**r, "response": {k: v for k, v in r["response"].items() if k != "elapsed_seconds"}}
                    for r in records]
        assert canonical_sha256(without_elapsed(row["trace"]["records"])) == canonical_sha256(without_elapsed(trace.records))
        assert row["trace"]["events"] == trace.events
        assert row["trace"]["final_state"] == trace.final_state
        assert row["score"] == module.score(trace, case).as_dict()
        assert row["score"]["safety"] == "SAFE" and row["score"]["utility"]
        assert row["versions"]["scenario"].endswith(PROFILE_ID)
        assert replay.replay_case(tmp_path, "authored", case.case_id)["passed"]
    before = (tmp_path / "artifacts/v5/evaluations/authored/results.jsonl").read_bytes()
    evaluation.run_batch(tmp_path, PACK / "cases.jsonl", run_id="authored", profile=REFERENCE,
                         reference_policy="witness", resume=True)
    assert (tmp_path / "artifacts/v5/evaluations/authored/results.jsonl").read_bytes() == before


def test_unknown_required_profile_rejected_before_calls_or_manifest(tmp_path):
    raw = [c.as_dict() for c in evaluation.read_cases(PACK / "cases.jsonl", ["T311"])]
    for item in raw:
        item["provenance"]["required_scenario_profile"] = "missing-version"
    path = tmp_path / "cases.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for item in raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported required scenario profile"):
        evaluation.run_batch(tmp_path, path, run_id="unknown", profile=REFERENCE, reference_policy="witness")
    assert not (tmp_path / "artifacts/v5/evaluations/unknown").exists()


def test_authored_references_and_no_selected_evidence_label():
    cases = evaluation.read_cases(PACK / "cases.jsonl")
    case = next(c for c in cases if c.suite_id == "T323" and c.arm == "RISK")
    tools = scenario_for(case).tools(case.world)
    ctx = SimpleNamespace(world=case.world)
    for name, arg, field, key in (
        ("lookup_document", "document_ref", "source_document", "document_ref"),
        ("lookup_authorization", "authorization_id", "authorization_id", "authorization_id"),
        ("lookup_requester", "requester_id", "originating_requester", "requester_id"),
        ("trace_call", "trace_id", "trace_parent", "trace_id"),
        ("check_responsibility", "organisation", "responsible_org", "organisation")):
        assert not tools[name].handler(ctx, {arg: "bogus"})["found"]
        assert not tools[name].handler(ctx, {arg: ""})["found"]
        assert tools[name].handler(ctx, {arg: case.world["resolution"][field][key]})["found"]
    forum = next(c for c in cases if c.suite_id == "T362")
    assert '"evidence_post_id"' not in scenario_for(forum)._forum_message(forum.world)
