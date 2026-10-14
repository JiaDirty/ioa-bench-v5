"""V4-S2 self-check: run the forked candidate tree standalone under a mock model
and prove the strict-retry classification contract holds end to end.

This imports the CANDIDATE sources (not the workspace), so it validates that the
fork is a coherent, runnable tree before any freeze decision.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path("D:/Project/ioa_codex_spec")
CAND = ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v2"
sys.path.insert(0, str(CAND / "src"))

from ioabench.core.types import RunState  # noqa: E402
from ioabench.runtime.batch import BatchRunner, TERMINAL_STATUSES, RESUMABLE_STATUSES  # noqa: E402
from ioabench.hashing import canonical_sha256
from ioabench.runtime.scientific_io import AttemptJournal, attempt_counter
from ioabench.runtime import construct_dispatch

results = {}


def check(name, ok, detail=""):
    results[name] = {"pass": bool(ok), "detail": detail}


# 1. enum
check("run_state_has_infra_interrupted", hasattr(RunState, "INFRA_INTERRUPTED")
      and str(RunState.INFRA_INTERRUPTED) == "INFRA_INTERRUPTED", str(getattr(RunState, "INFRA_INTERRUPTED", None)))

# 2. terminal/resumable sets
check("infra_interrupted_is_terminal", "INFRA_INTERRUPTED" in TERMINAL_STATUSES, sorted(TERMINAL_STATUSES))
check("invalid_output_is_terminal", "INVALID_MODEL_OUTPUT" in TERMINAL_STATUSES, "")
check("only_retryable_is_resumable", RESUMABLE_STATUSES == {"RETRYABLE_INFRA_FAILURE"}, sorted(RESUMABLE_STATUSES))

# 3. dispatch version bumped and classification table present
check("dispatch_version_1_0_2", construct_dispatch.DISPATCH_VERSION == "construct-dispatch-1.0.2",
      construct_dispatch.DISPATCH_VERSION)
check("infra_exception_table_present", len(construct_dispatch.INFRASTRUCTURE_EXCEPTIONS) >= 3,
      [c.__name__ for c in construct_dispatch.INFRASTRUCTURE_EXCEPTIONS])

# 4. resume rule semantics (pure function, no provider)
sandbox = Path(tempfile.mkdtemp(prefix="ioa-v4-selfcheck-"))
runner = BatchRunner(sandbox / "checkpoint.json", concurrency=1)
cases = {
    "retryable_zero_behaviour": ({"status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 0,
                                  "valid_model_behavior_observed": False, "infrastructure_failure": True}, True),
    "retryable_but_had_records": ({"status": "RETRYABLE_INFRA_FAILURE", "model_records_produced": 3,
                                   "valid_model_behavior_observed": False, "infrastructure_failure": True}, False),
    "infra_interrupted": ({"status": "INFRA_INTERRUPTED", "model_records_produced": 2,
                           "valid_model_behavior_observed": True, "infrastructure_failure": True}, False),
    "invalid_model_output": ({"status": "INVALID_MODEL_OUTPUT", "model_records_produced": 1,
                              "valid_model_behavior_observed": True, "infrastructure_failure": False}, False),
    "completed": ({"status": "COMPLETED", "model_records_produced": 5,
                   "valid_model_behavior_observed": True, "infrastructure_failure": False}, False),
    "failed": ({"status": "FAILED", "model_records_produced": 0,
                "valid_model_behavior_observed": False, "infrastructure_failure": False}, False),
}
for name, (entry, expected) in cases.items():
    check(f"resume_rule::{name}", runner.is_resumable(entry) is expected, f"expected={expected}")

# 5. AttemptJournal: records are flushed per record and attempts are never reused
journal_root = sandbox / "journalprobe"
jid = "deepseek-v4.1-flash-T999-2.0.0-v4-formal"
with AttemptJournal(journal_root, jid, "T999", "case-x", 1) as j:
    j.record({"agent_id": "a", "request": {}, "request_sha256": "x"})
    j.record({"agent_id": "a", "request": {}, "request_sha256": "y"})
    ev = j.partial_evidence()
check("journal_counts_records", ev["model_records_produced"] == 2, ev)
check("journal_marks_valid_behavior", ev["valid_model_behavior_observed"] is True, "")
check("journal_hash_recorded", ev["attempt_journal"]["sha256"] and len(ev["attempt_journal"]["sha256"]) == 64, "")
check("attempt_counter_advances", attempt_counter(journal_root, jid, "case-x") == 2, attempt_counter(journal_root, jid, "case-x"))
try:
    with AttemptJournal(journal_root, jid, "T999", "case-x", 1):
        pass
    check("journal_refuses_reuse", False, "attempt-1 was overwritable")
except FileExistsError:
    check("journal_refuses_reuse", True, "")

# 6. classification end to end through the real dispatcher path with a stub executor
from ioabench.errors import ProviderTransientError


def _call_dispatch(monkeypatch_exc, records_then_raise):
    """Drive execute_construct_case_sync with a patched executor via monkeypatch."""
    orig = construct_dispatch.execute_construct_case

    async def fake(root, suite, case, model, profile, *, run_id, auxiliary_models=None):
        if records_then_raise:
            from ioabench.runtime.scientific_io import record_model_io, TestedAgentSession
            from ioabench.models import ModelResponse
            from ioabench.sandbox import ActionBudget
            session = TestedAgentSession("lead", "org", "role", "p", ("t",), ActionBudget(max_rounds=4, max_model_calls=4, max_peer_messages=4, max_tool_calls=4))
            resp = ModelResponse(text="ok", tool_calls=(), finish_reason="stop", model_id="m", usage={}, provider_metadata={})
            record_model_io(session, {"messages": []}, resp)
        raise monkeypatch_exc

    construct_dispatch.execute_construct_case = fake
    try:
        return asyncio.run(construct_dispatch.execute_construct_case_strict(
            journal_root, "T999", {"candidate_id": f"case-{monkeypatch_exc.__class__.__name__}-{records_then_raise}"},
            object(), object(), run_id=jid))
    finally:
        construct_dispatch.execute_construct_case = orig


r_zero = _call_dispatch(ProviderTransientError("429"), records_then_raise=False)
r_after = _call_dispatch(ProviderTransientError("timeout"), records_then_raise=True)
r_noninfra = _call_dispatch(ValueError("bug"), records_then_raise=True)
check("zero_behaviour_infra_is_retryable", r_zero["status"] == "RETRYABLE_INFRA_FAILURE", r_zero["status"])
check("behaviour_then_infra_is_interrupted", r_after["status"] == "INFRA_INTERRUPTED", r_after["status"])
check("interrupted_retains_evidence", r_after["model_records_produced"] >= 1
      and r_after["partial_evidence_retained"] is True, r_after.get("model_records_produced"))
check("non_infra_is_failed", r_noninfra["status"] == "FAILED", r_noninfra["status"])
check("interrupted_not_resumable", runner.is_resumable(r_after) is False, "")

# 7. dispatch table covers 18 suites
check("dispatch_table_18_suites", len(construct_dispatch.RUNNERS) == 18, len(construct_dispatch.RUNNERS))

passed = sum(1 for v in results.values() if v["pass"])
total = len(results)
out = {"artifact": "V4_STRICT_RETRY_SELFCHECK", "pass": passed == total, "passed": passed, "total": total, "checks": results}
(ROOT / "artifacts/scientific_closure_v4").mkdir(parents=True, exist_ok=True)
(RD := ROOT / "artifacts/scientific_closure_v4/strict-retry-selfcheck-001.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"pass": out["pass"], "passed": passed, "total": total,
                  "failures": [k for k, v in results.items() if not v["pass"]]}, ensure_ascii=False, indent=1))
