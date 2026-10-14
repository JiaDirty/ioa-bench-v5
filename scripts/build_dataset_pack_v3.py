"""Build the authoritative Benchmark Dataset Pack (G3 freeze artifact).

Pins the authoritative frozen version of each of the 18 suites with the
content hash verified against the on-disk frozen manifest.  Refuses to write
if any suite fails verification.

Usage: python scripts/build_dataset_pack_v3.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# authoritative frozen versions (same map as reconcile_state.py / campaign maps)
from ioabench.frozen_versions import FROZEN_VERSIONS  # single source of truth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    suites: dict[str, dict] = {}
    for suite, version in FROZEN_VERSIONS.items():
        dataset_dir = ROOT / "data" / "datasets" / suite / version
        manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("version") != version or manifest.get("status") != "FROZEN":
            print(f"FAIL {suite}: manifest version/status mismatch ({manifest.get('version')}/{manifest.get('status')})")
            return 1
        cases = [line for line in (dataset_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(cases) != 90:
            print(f"FAIL {suite}: {len(cases)} cases, expected 90")
            return 1
        unique_ids = {json.loads(line)["candidate_id"] for line in cases}
        if len(unique_ids) != 90:
            print(f"FAIL {suite}: duplicate candidate ids")
            return 1
        suites[suite] = {"version": version,
                          "content_sha256": manifest["content_sha256"],
                          "generator_version": manifest.get("generation", {}).get("generator_version", ""),
                          "quality_gates": manifest.get("quality_gates", {})}
        print(f"OK {suite}@{version} sha={manifest['content_sha256'][:12]}")

    if args.dry_run:
        return 0
    pack = {"pack": "DATASET_PACK_v4", "immutable": True,
            "frozen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "authority": "authoritative frozen versions per STATE_RECONCILIATION; superseded versions retained on disk with provenance",
            "suites": suites}
    out = ROOT / "data" / "datasets" / "DATASET_PACK_v4.yaml"
    if out.exists():
        print(f"refusing to overwrite immutable pack: {out}")
        return 1
    out.write_text(yaml.safe_dump(pack, sort_keys=True, allow_unicode=True), encoding="utf-8")
    print(f"frozen: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
