"""Bounded variant of recover_history_source.py for exports whose preserved-byte
variant product exceeds the 200k combination guard.

Identical matching rule as the original: a source tree counts as recovered only
when its windows_snapshot_hash equals an independently recorded case source hash.
The only difference is scope: when the combinatorial preserved-byte search would
exceed the original 200_000-trial guard, this variant records that fact and runs
the direct literal replay only, instead of refusing to produce a report.
Historical commands are never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from scientific_closure import ROOT, windows_snapshot_hash, read_json, reference, write_new
from recover_history_source import source_path, literal_value, python_writes, combine_variants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-export", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--base-archive", type=Path, default=ROOT / "archive/deliveries/IoA-Bench-current-workspace-handoff-20260929-latest.zip",
                        help="ZIP whose src/contracts/config contents seed the reconstruction; must precede the export's edits")
    parser.add_argument("--combination-trial-guard", type=int, default=200_000)
    args = parser.parse_args()
    args.output_directory = args.output_directory.resolve()
    if not args.output_directory.is_relative_to(ROOT):
        raise ValueError("recovery artifacts must stay in this workspace")
    args.output_directory.mkdir(parents=True, exist_ok=False)
    old_archive = args.base_archive.resolve()
    with ZipFile(old_archive) as archive:
        initial = {n: archive.read(n) for n in archive.namelist() if n.startswith(("src/", "contracts/", "config/")) and not n.endswith("/") and "__pycache__" not in n.split("/")}
    files = dict(initial)
    prior = read_json(ROOT / "artifacts/scientific_closure_v3_2/source-byte-recovery-001.json")
    wanted = {g["recorded_source_sha256"] for row in prior["suites"] for g in row["groups"] if not g["source_bytes_resolved"]}
    history = read_json(args.history_export)
    mutations, recovered, ignored, context = [], {}, [], {}

    def save_bytes(data):
        sha = hashlib.sha256(data).hexdigest()
        target = args.output_directory / "source-bytes" / sha
        if not target.exists():
            target.parent.mkdir(exist_ok=True)
            with target.open("xb") as stream: stream.write(data)
        return reference(target)

    def save_match(digest, snapshot, origin):
        overrides = {path: save_bytes(content) for path, content in snapshot.items() if initial.get(path) != content}
        recovered[digest] = {"base_archive": reference(old_archive), "overrides": overrides,
            "file_hashes": {n: hashlib.sha256(v).hexdigest() for n, v in snapshot.items()}, "matched_at": origin}

    def commit(name, data):
        if re.search(rb"\bsk-[A-Za-z0-9_-]{20,}", data):
            raise ValueError("credential pattern in source candidate")
        before = files.get(name)
        if before == data: return
        files[name] = data
        digest = windows_snapshot_hash(files)
        mutations.append({**context, "path": name, "file_sha256": hashlib.sha256(data).hexdigest(), "source_sha256": digest, "content": save_bytes(data)})
        if digest in wanted and digest not in recovered:
            save_match(digest, files, dict(context))

    for message in history.get("messages", []):
        for wrapped in message.get("parts", []):
            part = wrapped.get("part", {}); state = part.get("state", {}); data = state.get("input", {})
            if part.get("type") != "tool" or state.get("status") != "completed": continue
            context = {"message_id": message.get("id"), "part_id": wrapped.get("id"),
                       "tool_end_unix_ms": state.get("time", {}).get("end"),
                       "input_sha256": hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
            try:
                if part.get("tool") in {"Edit", "Write"}:
                    name = str(source_path(data["file_path"]))
                    if part["tool"] == "Write": commit(name, data["content"].encode("utf-8"))
                    else:
                        original = files[name]; newline = "\r\n" if b"\r\n" in original else "\n"
                        old, new = data["old_string"].replace("\r\n", "\n"), data["new_string"].replace("\r\n", "\n")
                        text = original.decode("utf-8").replace("\r\n", "\n")
                        if text.count(old) != 1: raise ValueError("replacement is absent or ambiguous")
                        commit(name, text.replace(old, new, 1).replace("\n", newline).encode("utf-8"))
                elif part.get("tool") == "Bash":
                    command = data.get("command", "")
                    for match in re.finditer(r"python[^\n]*<<['\"]?(\w+)['\"]?\s*\n", command):
                        ending = re.search(r"(?m)^" + re.escape(match[1]) + r"\s*$", command[match.end():])
                        if ending:
                            source = command[match.end():match.end() + ending.start()]
                            skipped = python_writes(source, files, commit)
                            if skipped: ignored.append({**context, "unresolved_statements": skipped})
            except (ValueError, KeyError, TypeError, SyntaxError):
                if "src" in str(data.get("file_path", "")): ignored.append({**context, "reason": "source operation not reconstructed"})

    # Combination phase with the original 200k guard; on overflow this variant
    # documents the skip instead of aborting, and searches nothing.
    variants = {}
    for row in mutations:
        name = row["path"]
        values = variants.setdefault(name, [initial.get(name)])
        data = (ROOT / row["content"]["path"]).read_bytes()
        if data not in values: values.append(data)
    for name, values in variants.items():
        data = (ROOT / name).read_bytes() if (ROOT / name).is_file() else None
        if data not in values: values.append(data)
    variants.setdefault("config/synthetic_human.json", [None])
    for name, values in variants.items():
        data = (ROOT / name).read_bytes() if (ROOT / name).is_file() else None
        if data not in values: values.append(data)
    trials = 1
    for values in variants.values(): trials *= len(values)
    combination_status = "executed"
    matches = {}
    if trials > args.combination_trial_guard:
        combination_status = f"skipped_variant_product_{trials}_exceeds_guard_{args.combination_trial_guard}"
    else:
        trials, matches = combine_variants(initial, variants, wanted - recovered.keys())
        for digest, snapshot in matches.items():
            save_match(digest, snapshot, {"method": "preserved_byte_combinations", "variant_paths": sorted(variants)})

    report = {"artifact": "LITERAL_HISTORY_SOURCE_RECOVERY_BOUNDED", "pass": True, "provider_calls": 0,
              "historical_commands_executed": 0, "history_export_sha256": hashlib.sha256(args.history_export.read_bytes()).hexdigest(),
              "base_archive": reference(old_archive), "mutations": mutations, "recovered": recovered, "ignored": ignored,
              "combination_trials": trials, "combination_status": combination_status,
              "combination_trial_guard": args.combination_trial_guard,
              "variant_counts": {k: len(v) for k, v in variants.items()},
              "newly_resolved_cases": sum(g["case_count"] for row in prior["suites"] for g in row["groups"] if g["recorded_source_sha256"] in recovered),
              "scope": "Literal static reconstruction only; identical exact-hash acceptance rule as recover_history_source.py. Combination phase skipped when the preserved-byte variant product exceeds the original script's 200_000-trial guard; skipped searches search nothing and are recorded as such. Only exact matches to independently recorded source hashes count as recovered."}
    write_new(args.output_directory / "recovery.json", report)
    print(json.dumps({"source_mutations": len(mutations), "recovered_hashes": list(recovered), "newly_resolved_cases": report["newly_resolved_cases"], "combination_status": combination_status}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
