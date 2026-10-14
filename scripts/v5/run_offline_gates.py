"""Run and record the v5 multi-seed CONTROL/RISK offline gate matrix."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pkgutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.gates import check_pair  # noqa: E402
import ioabench.v5.suites as suites  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[5, 11, 101])
    parser.add_argument("--dataset-version", default="5.1.4-candidate-20261006")
    parser.add_argument("--out", type=Path, default=None,
                        help="report path; defaults to a timestamped file so reruns never overwrite prior reports")
    parser.add_argument("--overwrite", action="store_true",
                        help="explicitly allow writing an existing report path (verification reports are evidence)")
    args = parser.parse_args()
    if args.out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.out = ROOT / "artifacts" / "v5" / "gates" / f"offline-matrix-{stamp}.json"
    if args.out.exists() and not args.overwrite:
        raise SystemExit(f"REFUSED: report {args.out} already exists; pass --out with a new name "
                         f"or --overwrite explicitly (existing reports are evidence)")
    suite_rows = []
    for info in sorted(pkgutil.iter_modules(suites.__path__), key=lambda item: item.name):
        if not info.name.startswith("t"):
            continue
        module = importlib.import_module(f"ioabench.v5.suites.{info.name}")
        failures = []
        pairs = 0
        for seed in args.seeds:
            for control, risk in module.generate(seed=seed):
                result = check_pair(control, risk)
                pairs += 1
                if not result["passed"]:
                    failures.append({"seed": seed, "pair_id": control.pair_id, "failures": result["failures"]})
        suite_rows.append({"suite": module.SUITE_ID, "pairs_checked": pairs, "failures": failures,
                           "passed": not failures,
                           "source_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()})
        print(f"{module.SUITE_ID}: {pairs} pairs, {len(failures)} failed", flush=True)
    shared = [ROOT / "src" / "ioabench" / "v5" / "gates.py",
              ROOT / "src" / "ioabench" / "v5" / "core" / "case.py",
              ROOT / "src" / "ioabench" / "v5" / "core" / "firewall.py"]
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "seeds": args.seeds,
              "dataset_version_context": args.dataset_version,
              "gates_version": "v5-pair-gates-1.0.0",
              "shared_sources_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in shared},
              "suites": suite_rows,
              "total_pairs": sum(row["pairs_checked"] for row in suite_rows),
              "total_failures": sum(len(row["failures"]) for row in suite_rows),
              "passed": all(row["passed"] for row in suite_rows)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"TOTAL: {report['total_pairs']} pairs, {report['total_failures']} failures; report={args.out}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
