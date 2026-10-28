"""Write the R2 DEV_POOL_INDEX.jsonl (accepted development pairs of this round)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "artifacts/v5/data_factory/tree_factory_r2/tf-r2-20261024-r1"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    rows = []
    for sub in ("m4_t321", "ab"):
        base = RUN / sub
        if not (base / "reviews").exists():
            continue
        for admission_path in sorted((base / "reviews").glob("*/ADMISSION.json")):
            record = read(admission_path)
            if record.get("status") != "DEV_ACCEPTED":
                continue
            candidate = admission_path.parent.name
            result = read(base / "candidates" / candidate / "RESULT.json")
            binding_path = base / "candidates" / candidate / "BUSINESS_BINDING.json"
            binding = read(binding_path) if binding_path.exists() else {}
            rows.append({
                "candidate": candidate,
                "suite": candidate.split("-")[1],
                "route": result.get("route"),
                "admission": "DEV_ACCEPTED",
                "scope": "DEVELOPMENT_EXPLORATORY_SAME_FAMILY",
                "formal_accepted": False,
                "same_model_audit_independent_science": False,
                "simulation_only": candidate.startswith("R2-T36"),
                "business_root": binding.get("root"),
                "business_workflow_hash": binding.get("canonical_workflow_hash"),
                "mechanism_signature_sha256": result.get("structural_signature_sha256"),
                "history_statuses": result.get("history_statuses"),
                "replay_count": result.get("reference_and_replay_count"),
                "evidence": f"{sub}/candidates/{candidate}"})
    with (RUN / "DEV_POOL_INDEX.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"dev_pool_rows": len(rows), "generated_utc":
                      datetime.now(timezone.utc).isoformat()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
