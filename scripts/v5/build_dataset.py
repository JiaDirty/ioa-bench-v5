"""Build a v5 candidate dataset: generate, gate every pair, write accepted cases + rejections + manifest.

Usage: python scripts/v5/build_dataset.py --version 5.1.0 --seed 20261005 [--suites T311 ...]

Output: data/v5/datasets/<suite>/<version>/{cases.jsonl, rejected.jsonl, manifest.json}
A pair is written only if ioabench.v5.gates.check_pair passes; rejected pairs keep their reasons. Gates are never
relaxed to fill the quota (AGENTS.md section 4.9); shortfalls are reported in the manifest.
Existing output directories are never overwritten (datasets are immutable): the script refuses to run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5 import V5_LAYER_VERSION  # noqa: E402
from ioabench.v5.core.engine import ENGINE_VERSION  # noqa: E402
from ioabench.v5.core.firewall import FIREWALL_VERSION  # noqa: E402
from ioabench.v5.gates import GATES_VERSION, check_pair  # noqa: E402
from ioabench.v5.suites import implemented, load  # noqa: E402

TARGET_PAIRS = 60


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(suite: str, version: str, seed: int) -> dict[str, object]:
    module = load(suite)
    out = ROOT / "data" / "v5" / "datasets" / suite / version
    if out.exists():
        raise SystemExit(f"{out} exists; v5 datasets are immutable — choose a new version")
    out.mkdir(parents=True)
    accepted, rejected = [], []
    for control, risk in module.generate(seed=seed):
        report = check_pair(control, risk)
        if report["passed"]:
            accepted += [control, risk]
        else:
            rejected.append({"pair_id": control.pair_id, "failures": report["failures"]})
    with (out / "cases.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for case in accepted:
            stream.write(json.dumps(case.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    with (out / "rejected.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for row in rejected:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    pairs = len(accepted) // 2
    manifest = {"suite_id": suite, "dataset_version": version, "seed": seed,
                "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "pairs": pairs,
                "cases": len(accepted), "rejected_pairs": len(rejected), "target_pairs": TARGET_PAIRS,
                "shortfall": max(0, TARGET_PAIRS - pairs),
                "versions": {"layer": V5_LAYER_VERSION, "engine": ENGINE_VERSION, "firewall": FIREWALL_VERSION,
                             "gates": GATES_VERSION, "scenario": module.SCENARIO_VERSION, "scorer": module.SCORER_VERSION,
                             "generator": module.GENERATOR_VERSION},
                "files": {"cases.jsonl": _sha(out / "cases.jsonl"), "rejected.jsonl": _sha(out / "rejected.jsonl")},
                "case_sha256": [c.content_sha256() for c in accepted], "status": "CANDIDATE_NOT_FROZEN"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {k: manifest[k] for k in ("suite_id", "pairs", "rejected_pairs", "shortfall")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="5.1.0")
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--suites", nargs="*", default=None)
    args = parser.parse_args()
    for suite in args.suites or implemented():
        print(json.dumps(build(suite, args.version, args.seed)))


if __name__ == "__main__":
    main()
