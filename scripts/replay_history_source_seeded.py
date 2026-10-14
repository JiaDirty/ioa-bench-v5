"""Seeded literal replay of one history export over an older source baseline.

The baseline ZIP predates the creation of some source files; those files are
seeded with candidate bytes (absent, a later archive's bytes, current disk bytes)
so that in-export Edit operations can reconstruct. Acceptance rule is unchanged:
a tree counts as resolved only when its windows_snapshot_hash equals an
independently recorded case source hash. Phase 1 seeds every missing file with
the later archive's bytes; if the reconstructed final tree then equals the later
archive's own tree (an independent known hash), the seed choice is validated.
Otherwise phase 2 searches seed combinations within a bounded trial guard.
Historical commands are never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path
import re
from zipfile import ZipFile

from scientific_closure import ROOT, windows_snapshot_hash, read_json, reference, write_new
from recover_history_source import source_path, python_writes


def load_archive_files(archive: Path):
    with ZipFile(archive) as z:
        return {n: z.read(n) for n in z.namelist()
                if n.startswith(("src/", "contracts/", "config/")) and not n.endswith("/")
                and "__pycache__" not in n.split("/")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-export", type=Path, required=True)
    parser.add_argument("--base-archive", type=Path, required=True, help="older baseline; must precede the export's edits")
    parser.add_argument("--seed-archive", type=Path, required=True, help="later archive supplying candidate bytes for files missing from the baseline")
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--combination-trial-guard", type=int, default=200_000)
    args = parser.parse_args()
    args.output_directory = args.output_directory.resolve()
    if not args.output_directory.is_relative_to(ROOT):
        raise ValueError("recovery artifacts must stay in this workspace")
    args.output_directory.mkdir(parents=True, exist_ok=False)
    args.base_archive = args.base_archive.resolve()
    args.seed_archive = args.seed_archive.resolve()

    base_files = load_archive_files(args.base_archive)
    seed_files = load_archive_files(args.seed_archive)
    missing = sorted(set(seed_files) - set(base_files))
    prior = read_json(ROOT / "artifacts/scientific_closure_v3_2/source-byte-recovery-001.json")
    wanted = {g["recorded_source_sha256"] for row in prior["suites"] for g in row["groups"] if not g["source_bytes_resolved"]}
    base_tree = windows_snapshot_hash(base_files)
    seed_archive_tree = windows_snapshot_hash(seed_files)
    history = read_json(args.history_export)

    ops = []
    for message in history.get("messages", []):
        for wrapped in message.get("parts", []):
            part = wrapped.get("part", {}); state = part.get("state", {}); data = state.get("input", {})
            if part.get("type") != "tool" or state.get("status") != "completed": continue
            if part.get("tool") not in {"Edit", "Write"}: continue
            try:
                name = str(source_path(data["file_path"]))
            except (ValueError, KeyError):
                continue
            ops.append({"context": {"message_id": message.get("id"), "part_id": wrapped.get("id"),
                                    "tool_end_unix_ms": state.get("time", {}).get("end")},
                        "tool": part["tool"], "path": name, "data": data})

    def save_bytes(data: bytes) -> dict:
        sha = hashlib.sha256(data).hexdigest()
        target = args.output_directory / "source-bytes" / sha
        if not target.exists():
            target.parent.mkdir(exist_ok=True)
            with target.open("xb") as stream: stream.write(data)
        return reference(target)

    def run_pass(seed_choice):
        files = dict(base_files)
        for name, value in zip(missing, seed_choice):
            if value is not None: files[name] = value
        mutations, ignored, matches = [], [], {}
        for op in ops:
            name, tool, data = op["path"], op["tool"], op["data"]
            before = files.get(name)
            try:
                if tool == "Write":
                    new = data["content"].encode("utf-8")
                else:
                    if before is None: raise ValueError("edit target absent")
                    newline = "\r\n" if b"\r\n" in before else "\n"
                    old, new = data["old_string"].replace("\r\n", "\n"), data["new_string"].replace("\r\n", "\n")
                    text = before.decode("utf-8").replace("\r\n", "\n")
                    if text.count(old) != 1: raise ValueError("replacement is absent or ambiguous")
                    new = text.replace(old, new, 1).replace("\n", newline).encode("utf-8")
                if re.search(rb"\bsk-[A-Za-z0-9_-]{20,}", new):
                    raise ValueError("credential pattern in source candidate")
                if before == new: continue
                files[name] = new
                digest = windows_snapshot_hash(files)
                mutations.append({**op["context"], "path": name, "tool": tool,
                                  "file_sha256": hashlib.sha256(new).hexdigest(),
                                  "source_sha256": digest, "content": save_bytes(new)})
                if digest in wanted and digest not in matches:
                    matches[digest] = {"at_mutation": len(mutations), "matched_path": name}
            except (ValueError, KeyError, TypeError, SyntaxError):
                ignored.append({**op["context"], "path": name, "tool": tool,
                                "reason": "source operation not reconstructed"})
        return files, mutations, ignored, matches

    # Phase 1: seed every missing file with the later archive's bytes.
    phase1_seed = [seed_files[n] for n in missing]
    files1, muts1, ign1, matches1 = run_pass(phase1_seed)
    final1 = windows_snapshot_hash(files1)
    phase1_validated = final1 == seed_archive_tree

    phase2 = None
    matches = matches1
    muts, ign = muts1, ign1
    if not phase1_validated:
        # Phase 2: bounded seed-combination search (absent / later-archive bytes / current disk bytes).
        variants = []
        for name in missing:
            values = [None, seed_files[name]]
            current = (ROOT / name)
            if current.is_file():
                data = current.read_bytes()
                if data not in values: values.append(data)
            variants.append(values)
        trials = 1
        for v in variants: trials *= len(v)
        if trials > args.combination_trial_guard:
            phase2 = {"combination_trials": trials, "status": f"skipped_guard_{args.combination_trial_guard}"}
        else:
            found = {}
            for choice in product(*variants):
                if all(v is None for v in choice): continue
                files, muts2, ign2, matches2 = run_pass(choice)
                if windows_snapshot_hash(files) == seed_archive_tree:
                    for digest, info in matches2.items():
                        if digest not in found:
                            info = dict(info); info["seed_choice"] = [v is not None and hashlib.sha256(v).hexdigest()[:12] for v in choice]
                            found[digest] = info
            phase2 = {"combination_trials": trials, "status": "executed", "validated_matches": found}
            matches = {**matches1, **found}

    report = {"artifact": "SEEDED_HISTORY_SOURCE_REPLAY", "pass": bool(matches) or phase1_validated,
              "provider_calls": 0, "historical_commands_executed": 0,
              "history_export_sha256": hashlib.sha256(args.history_export.read_bytes()).hexdigest(),
              "base_archive": reference(args.base_archive), "seed_archive": reference(args.seed_archive),
              "base_tree_sha256": base_tree, "seed_archive_tree_sha256": seed_archive_tree,
              "seeded_files": missing, "source_operations": len(ops),
              "phase1": {"final_tree_sha256": final1, "validated_against_seed_archive": phase1_validated,
                         "mutations": muts1, "ignored": ign1, "matches": matches1},
              "phase2": phase2, "recovered": matches,
              "newly_resolved_cases": sum(g["case_count"] for row in prior["suites"] for g in row["groups"]
                                          if g["recorded_source_sha256"] in matches),
              "scope": "Literal static reconstruction with seeded missing files; never executes historical commands. Only exact windows_snapshot_hash equality with independently recorded case source hashes counts as recovered; the seed choice is validated against the later archive's own independent tree hash."}
    write_new(args.output_directory / "replay.json", report)
    print(json.dumps({"source_operations": len(ops), "phase1_mutations": len(muts1), "phase1_ignored": len(ign1),
                      "phase1_final_tree": final1[:16], "phase1_validated": phase1_validated,
                      "recovered": {k[:12]: v for k, v in matches.items()},
                      "newly_resolved_cases": report["newly_resolved_cases"],
                      "phase2": (phase2 or {}).get("status")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
