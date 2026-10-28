"""Verify retained Round02 evidence and terminal resume with a port that forbids calls."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).parent)]
from benchmark_provider_round02 import Study
from compare_round02_efforts import quality
from compare_auxiliary_models import read, sha
from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.auxiliary_runtime import engineering_contracts
from ioabench.v5.evaluation import atomic_json


class NoNetwork:
    calls = 0

    async def generate(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("No request permitted during evidence/resume verification")


async def verify(out):
    previous = ROOT / "artifacts/v5/provider_benchmark/round02-20261020T002308CST"
    sums = {**read(previous / "BASELINE.json")["protected_files"], **read(out / "PREVIOUS_ROUND_SHA256.json")}
    missing = [name for name in sums if not (ROOT / name).is_file()]
    changed = [name for name, expected in sums.items() if (ROOT / name).is_file() and sha(ROOT / name) != expected]
    atomic_json(out / "PROTECTED_HISTORY.json", {"status": "FAIL" if changed or missing else "PASS",
        "checked": len(sums), "changed": changed, "missing": missing,
        "scope": "R3/Round01/prior Round02 baseline plus all prior Round02 files"})
    assert not changed and not missing

    old = read(previous / "HISTORICAL_UNRESOLVED_REGISTER.json")
    records = [read(path) for path in out.rglob("attempt-*.json")]
    assert len(old["requests"]) == 4
    assert not {r["request_sha256"] for r in old["requests"]} & {r["request_sha256"] for r in records}
    atomic_json(out / "HISTORICAL_UNRESOLVED_REGISTER.json", {**old, "resends": 0,
        "current_request_hashes_checked": len(records), "prior_register_sha256": sha(previous / "HISTORICAL_UNRESOLVED_REGISTER.json")})

    stop_time = datetime.fromisoformat(read(out / "STOP.json")["at_utc"])
    late, event_count = [], 0
    for path in out.rglob("AIHUBMIX_ATTEMPTS.jsonl"):
        digest = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            actual = row.pop("event_sha256")
            assert row["previous_event_sha256"] == digest and canonical_sha256(row) == actual
            digest = actual
            event_count += 1
            if row["event"] == "REQUEST_STARTED" and datetime.fromisoformat(row["at_utc"]) > stop_time:
                late.append({"ledger": path.relative_to(out).as_posix(), "event": row})
    assert not late, "A paid request began after the global auth stop"
    assert read(out / "r1_END.json")["at_utc"] < read(out / "r2_START.json")["at_utc"]
    files = [p for folder in ("protocols", "quality", "wire", "s1-completion") for p in (out / folder).rglob("*")
             if p.is_file() and not p.name.endswith(".lock")]
    before = {p: sha(p) for p in files}
    port = NoNetwork()
    study = Study(out, port)
    count_r = 0
    for path in (out / "protocols").glob("*/*/RESULT.json"):
        result = read(path)
        assert await study.protocol(result["config"], result["batch"]) == result
        count_r += 1
    plan = read(out / "BENCHMARK_TASKSET_FROZEN.json")
    count_q = 0
    for path in (out / "quality").glob("*/*/RESULT.json"):
        result = read(path)
        config = next(c for c in plan["configs"] if c["id"] == result["config_id"])
        task = next(t for t in plan["tasks"] if t["id"] == result["task"])
        assert await quality(study, config, task) == result
        count_q += 1
    assert not port.calls and all(sha(path) == expected for path, expected in before.items())
    routing = out / "AUXILIARY_ROUTING_PROFILE.json"
    assert read(routing)["contracts"] == read(routing)["auditor_contracts"] == []
    try:
        engineering_contracts(routing, workspace=ROOT, model_ids=["mimo-v2.6-pro"])
    except ValueError as exc:
        assert "no complete engineering comparison" in str(exc)
        routing_result = str(exc)
    else:
        raise AssertionError("Incomplete quality results must not activate generator routes")
    atomic_json(out / "REPLAY_RESUME.json", {"status": "PASS", "port_calls": port.calls,
        "protocol_terminal_results": count_r, "quality_terminal_results": count_q,
        "raw_files_byte_verified": len(files), "ledger_events_verified": event_count,
        "requests_started_after_auth_stop": late, "historical_unresolved_resends": 0,
        "incomplete_live_routing_rejected": routing_result, "r1_r2_nonoverlap": "PASS",
        "live_healthy_fallback": "NOT_RUN_AUTH_STOP", "long_context_B": "NOT_RUN_AUTH_STOP"})
    print(json.dumps({"protected": len(sums), "terminal_protocol": count_r, "terminal_quality": count_q,
                      "port_calls": port.calls, "history_resends": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    asyncio.run(verify(parser.parse_args().out.resolve()))
