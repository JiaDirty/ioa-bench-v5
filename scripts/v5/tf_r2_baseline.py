"""R2 M0: baseline snapshot + isolated new run directory (GOAL R2-G0).

Reads only. Binds the new run to the current HEAD and the sealed R1 history
(old STOP.json / REQUEST_LEDGER.jsonl / 7 accepted pairs stay read-only).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.v5.evaluation import atomic_json  # noqa: E402

R1 = ROOT / "artifacts/v5/tree_factory/tf-20261024-r1"
SEALED_INDEX = ROOT / "artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json"
RUN_ID = "tf-r2-20261024-r1"
OUT = ROOT / "artifacts/v5/data_factory/tree_factory_r2" / RUN_ID


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(("git", "-C", str(ROOT), *args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def main() -> None:
    load_workspace_env(ROOT / ".env")
    import os
    head = git("rev-parse", "HEAD")
    dirty = [line for line in git("status", "--porcelain").splitlines() if line.strip()]
    untracked_only = all(line.startswith("??") for line in dirty)
    r1_stop = R1 / "STOP.json"
    ledger = R1 / "REQUEST_LEDGER.jsonl"
    unresolved = []
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("event") == "REQUEST_FAILED" and row.get("category") in {"REQUEST_UNRESOLVED", "UNKNOWN"}:
                unresolved.append(row.get("request_id"))
    accepted = sorted(path.parent.name for path in R1.glob("**/ADMISSION.json")
                      if json.loads(path.read_text(encoding="utf-8")).get("status") == "DEV_ACCEPTED")
    accepted_pairs = len(accepted)
    baseline = {
        "version": "ioabench.v5.treefactory.r2.baseline/1.0.0",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": {"head": head, "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty_entries": len(dirty), "dirty_untracked_only": untracked_only},
        "r1_sealed": {"run": "artifacts/v5/tree_factory/tf-20261024-r1",
                      "stop_category": json.loads(r1_stop.read_text(encoding="utf-8"))["category"] if r1_stop.exists() else None,
                      "stop_sha256": sha(r1_stop) if r1_stop.exists() else None,
                      "ledger_sha256": sha(ledger) if ledger.exists() else None,
                      "unresolved_request_ids": unresolved,
                      "accepted_pairs_r1": accepted_pairs,
                      "accepted_candidates_r1": accepted,
                      "policy": "READ_ONLY_NEVER_REWRITE_NEVER_RESEND"},
        "sealed_history_index": {"path": SEALED_INDEX.relative_to(ROOT).as_posix(),
                                 "sha256": sha(SEALED_INDEX),
                                 "records": len(json.loads(SEALED_INDEX.read_text(encoding="utf-8"))["records"])},
        "provider": {"aihubmix_api_key_present": bool(os.environ.get("AIHUBMIX_API_KEY")),
                     "key_source": ".env via load_workspace_env; value never logged"},
        "writer_lock": {"path": "artifacts/v5/data_factory/.writer.lock",
                        "held": (ROOT / "artifacts/v5/data_factory/.writer.lock").exists()},
        "new_run": {"id": RUN_ID, "directory": OUT.relative_to(ROOT).as_posix(),
                    "scope": "R2 new candidates only; no R1 file is opened for write"},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT / "BASELINE_R2.json", baseline)
    contract = {
        "version": "ioabench.v5.treefactory.r2.run-contract/1.0.0",
        "run_id": RUN_ID,
        "baseline_head": head,
        "live_model": "deepseek-v4.1-flash-1017",
        "budget_gate": "DISABLED_BY_USER_AUTHORIZATION (no USD soft/hard stop; usage still recorded)",
        "output_profile": {"base_max_tokens": 131072, "complex_max_tokens": 262144,
                           "probe_ceiling": 393216, "effort_default": "high", "effort_complex": "max"},
        "request_discipline": {"new_request_ids_only": True, "no_resend_unresolved": True,
                               "old_ledgers_read_only": True},
        "route": "tree_ir_runtime_v2 (mandatory BusinessBinding -> MechanismIR.validate == [] "
                 "-> capability validate -> blueprint_from_ir -> existing compilers)",
        "baseline_route_readonly": "baseline_4stage kept for the same-task comparison arm",
        "admission": "DEV_ACCEPTED (development pool; same-model audit is not independent science)",
    }
    atomic_json(OUT / "R2_RUN_CONTRACT.json", contract)
    print(json.dumps({"head": head, "untracked_only": untracked_only,
                      "r1_unresolved": unresolved, "r1_accepted_pairs": accepted_pairs,
                      "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
