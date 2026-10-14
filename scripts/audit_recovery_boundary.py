"""Bounded offline search for retained source trees and original attempt evidence."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
from pathlib import Path, PurePosixPath
import re
from zipfile import ZipFile

from scientific_closure import ROOT, read_json, reference, sha256, windows_snapshot_hash, write_new

BASE = ROOT / "artifacts/scientific_closure_v3_2"
MARKER = "src/ioabench/__init__.py"


def nested_snapshots(archive):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("ambiguous duplicate ZIP members")
    roots = sorted({name[:-len(MARKER)] for name in names if name.endswith(MARKER) and name != MARKER})
    rows = []
    for prefix in roots:
        files = {}
        for name in names:
            if not name.startswith(tuple(prefix + d + "/" for d in ("src", "contracts", "config"))):
                continue
            relative = name[len(prefix):]
            if ":" in name or "\\" in name or ".." in PurePosixPath(name).parts or name.startswith("/"):
                raise ValueError("noncanonical source member path")
            if not name.endswith("/") and "__pycache__" not in name.split("/"):
                files[relative] = archive.read(name)
        rows.append({"prefix": prefix, "file_count": len(files), "source_sha256": windows_snapshot_hash(files)})
    return rows


def observation_time_diagnostic(results, observation):
    """A display time is not the generation time of a saved result snapshot."""
    threshold = observation["tool_time"]["start"] / 1000
    after, missing = Counter(), 0
    for result in results.values():
        times = [datetime.fromisoformat(e["event_time"].replace("Z", "+00:00")).timestamp()
                 for e in result.get("replay", {}).get("timeline", []) if e.get("event_time")]
        if not times:
            missing += 1
        elif min(times) > threshold:
            after[result["status"]] += 1
    return {"tool_start_unix_ms": observation["tool_time"]["start"],
            "retained_trajectories_starting_later": dict(after), "missing_timeline": missing,
            "can_identify_original_invalid_case_ids": False,
            "reason": "Tool observation time does not pin when results.json was saved; no attempt identities or clock equivalence are established."}


def build(history_export):
    prior_path = BASE / "source-byte-recovery-001.json"
    review_path = BASE / "source-semantic-review-002.json"
    impact_path = ROOT / "artifacts/gates/V32_S1_POLICY_IMPACT_v2.json"
    prior, review, impact = map(read_json, (prior_path, review_path, impact_path))
    historical = impact["historical_observations"]
    if sha256(history_export) != historical["external_export_sha256"]:
        raise ValueError("history export differs from policy evidence")
    history = read_json(history_export)
    parts = {w["id"]: w["part"] for m in history["messages"] for w in m.get("parts", [])}
    archive_rows = []
    for item in prior["archives"]:
        path = ROOT / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError("archive differs from recorded recovery input")
        with ZipFile(path) as archive:
            archive_rows.append({"archive": reference(path), "nested_snapshots": nested_snapshots(archive)})
    disk_rows, excluded = [], []
    for marker in sorted(ROOT.rglob(MARKER)):
        directory = marker.parents[2]
        if directory == ROOT:
            continue
        if directory == BASE / "corrective-candidate":
            excluded.append({"path": directory.relative_to(ROOT).as_posix(), "reason": "new isolated corrective candidate, not historical evidence"})
            continue
        files = {p.relative_to(directory).as_posix(): p.read_bytes() for d in ("src", "contracts", "config")
                 for p in (directory / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        disk_rows.append({"path": directory.relative_to(ROOT).as_posix(), "file_count": len(files),
                          "source_sha256": windows_snapshot_hash(files)})
    found = {r["source_sha256"] for a in archive_rows for r in a["nested_snapshots"]} | {r["source_sha256"] for r in disk_rows}
    matches = [r for r in review["remaining_source_groups"] if r["source_sha256"] in found]
    candidate_stores = [reference(p) for p in sorted(ROOT.rglob("*")) if p.is_file()
                        and p.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".tmp", ".bak", ".old"}]
    formal_files, temporal = [], []
    for changed in historical["confirmed_invalid_count_decreases"]:
        path = ROOT / changed["final_evidence"]["path"]
        if sha256(path) != changed["final_evidence"]["sha256"]:
            raise ValueError("formal result differs from policy evidence")
        formal_files.append({"suite": changed["suite"], "files": [reference(p) for p in sorted(path.parent.rglob("*")) if p.is_file()]})
        obs = next(o for o in historical["observations"] if o["part_id"] == changed["earlier_part_id"])
        part = parts[obs["part_id"]]
        state = part.get("state", {})
        if state.get("status") != "completed" or obs["quoted_output_line"] not in state.get("output", "").splitlines():
            raise ValueError("historical observation no longer matches exported completed tool output")
        temporal.append({"suite": changed["suite"], "part_id": obs["part_id"],
                         "tool_input_sha256": obs["tool_input_sha256"],
                         "command_mentions_results_json": "results.json" in state.get("input", {}).get("command", ""),
                         "minimum_previously_invalid_no_longer_invalid": changed["minimum_previously_invalid_no_longer_invalid"],
                         **observation_time_diagnostic(read_json(path), obs)})
    output_hits = []
    for part_id, part in parts.items():
        state = part.get("state", {})
        output = state.get("output", "")
        if part.get("type") != "tool" or state.get("status") != "completed" or not isinstance(output, str) or "INVALID_MODEL_OUTPUT" not in output:
            continue
        ids = sorted(set(re.findall(r'\b(T3\d{2}-[a-z0-9-]+)[\s"\x27:]+INVALID_MODEL_OUTPUT\b', output)))
        output_hits.append({"part_id": part_id, "tool": part.get("tool"),
                            "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
                            "explicit_case_status_mentions": ids,
                            "formal_attempt_identity_established": False})
    paths = ["src/ioabench/cli.py", "src/ioabench/runtime/batch.py", "src/ioabench/runtime/construct_dispatch.py",
             "src/ioabench/runtime/scientific_io.py", "src/ioabench/runtime/discovery_selection.py",
             "src/ioabench/models/aihubmix.py", "src/ioabench/replay/bundle.py"]
    return {"artifact": "RETAINED_EVIDENCE_RECOVERY_BOUNDARY", "version": 1,
            "search_completed": True, "canonical_acceptance": False, "provider_calls": 0,
            "historical_commands_executed": 0, "inputs": [reference(p) for p in (prior_path, review_path, impact_path)],
            "history_export_sha256": sha256(history_export), "archive_search": archive_rows,
            "disk_source_search": disk_rows, "excluded_generated_sources": excluded,
            "new_source_match_candidates": matches, "candidate_store_files": candidate_stores,
            "formal_storage_inventory": formal_files, "historical_invalid_output_mentions": output_hits,
            "observation_time_diagnostics": temporal, "persistence_code_evidence": [reference(ROOT / p) for p in paths],
            "limits": ["Source roots are identified by src/ioabench/__init__.py; partial trees without this marker are outside this search.",
                       "Database, backup and temporary-file scan covers this workspace only and the stated filename suffixes.",
                       "The 39-style output inventory is a lexical search, not proof that all earlier attempts can be recovered.",
                       "No scientific source or historical Run, Release, Gate or dataset is changed.",
                       "A negative bounded search does not prove that evidence is absent outside this scope."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(BASE.resolve()) or output.exists():
        raise ValueError("use a new recovery artifact path inside scientific_closure_v3_2")
    report = build(args.history_export)
    write_new(output, report)
    print({"search_completed": True, "nested_zip_trees": sum(len(a["nested_snapshots"]) for a in report["archive_search"]),
           "disk_trees": len(report["disk_source_search"]), "source_match_candidates": len(report["new_source_match_candidates"]),
           "candidate_stores": len(report["candidate_store_files"]), "output": output.relative_to(ROOT).as_posix()})


if __name__ == "__main__":
    main()
