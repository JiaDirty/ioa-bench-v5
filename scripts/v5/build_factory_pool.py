"""Build or verify an immutable development pool; no model calls or formal freeze."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.ai_generation.pool import build_pool, verify_pool


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--assignments", type=Path,
        help="JSON list: directory, split; optional calibration, source_files, auditor_qualification={preflight,judge_controls}")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--source-sha256")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        report = verify_pool(args.output)
    else:
        if not all((args.assignments, args.registry, args.source_sha256)):
            parser.error("build requires --assignments --registry --source-sha256")
        report = build_pool(ROOT, args.output, json.loads(args.assignments.read_text(encoding="utf-8")),
                            registry_path=args.registry, expected_source_sha256=args.source_sha256)
    print(json.dumps({key: report[key] for key in ("status", "content_sha256", "entries", "cases", "layer_case_counts", "split_status", "formal_accepted")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
