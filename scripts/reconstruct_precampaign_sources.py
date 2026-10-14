"""Exact reconstruction of pre-campaign source trees from literal edit history.

Per-file content evolution inside the export is independent of every other file,
so each file's session-start content is first derived and forward-verified in
isolation: the later archive's bytes are the known post-chain state (the archive
postdates the export's last edit of the file and predates all later edits of
it), Edit chains are inverted (branching over occurrences, forward-verified per
candidate), and a candidate survives only when replaying the file's full chain
on it reproduces the archive bytes exactly. Tree states at every commit are then
enumerated over the small remaining option sets (drift candidates, presence of
files the baseline predates) and accepted only on exact windows_snapshot_hash
equality with independently recorded case source hashes. Historical commands
are never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path, PureWindowsPath
import re
from zipfile import ZipFile

from scientific_closure import ROOT, read_json, reference, write_new
from recover_history_source import source_path


def load_archive_files(archive: Path):
    with ZipFile(archive) as z:
        return {n: z.read(n) for n in z.namelist()
                if n.startswith(("src/", "contracts/", "config/")) and not n.endswith("/")
                and "__pycache__" not in n.split("/")}


def lf(data: bytes) -> str:
    return data.decode("utf-8").replace("\r\n", "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-export", type=Path, required=True)
    parser.add_argument("--base-archive", type=Path, required=True)
    parser.add_argument("--seed-archive", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--max-branch-candidates", type=int, default=4096)
    args = parser.parse_args()
    args.output_directory = args.output_directory.resolve()
    if not args.output_directory.is_relative_to(ROOT):
        raise ValueError("recovery artifacts must stay in this workspace")
    args.output_directory.mkdir(parents=True, exist_ok=False)
    args.base_archive = args.base_archive.resolve()
    args.seed_archive = args.seed_archive.resolve()

    base_files = load_archive_files(args.base_archive)
    seed_files = load_archive_files(args.seed_archive)
    from scientific_closure import windows_snapshot_hash
    seed_archive_tree = windows_snapshot_hash(seed_files)
    prior = read_json(ROOT / "artifacts/scientific_closure_v3_2/source-byte-recovery-001.json")
    wanted = {g["recorded_source_sha256"] for row in prior["suites"] for g in row["groups"] if not g["source_bytes_resolved"]}
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
            ops.append({"index": len(ops), "path": name, "tool": part["tool"], "data": data,
                        "context": {"message_id": message.get("id"), "part_id": wrapped.get("id"),
                                    "tool_end_unix_ms": state.get("time", {}).get("end")}})

    files_of_ops = {}
    for op in ops:
        files_of_ops.setdefault(op["path"], []).append(op)

    # ---- per-file candidate derivation ----
    file_options = {}   # name -> list of tracks; track = {"label", "states": {op_index: content or None}}
    inversion_report = {}
    for name, file_ops in files_of_ops.items():
        crlf = b"\r\n" in seed_files.get(name, base_files.get(name, b""))
        tracks = []
        first = file_ops[0]
        if first["tool"] == "Write":
            # content before the Write is not needed for any target tree; a single
            # track starts at the Write.
            content = first["data"]["content"].encode("utf-8")
            states = {}
            ok = True
            cur = content
            for op in file_ops[1:]:
                if op["tool"] == "Write":
                    cur = op["data"]["content"].encode("utf-8")
                else:
                    text = cur.decode("utf-8").replace("\r\n", "\n")
                    old = op["data"]["old_string"].replace("\r\n", "\n")
                    new = op["data"]["new_string"].replace("\r\n", "\n")
                    if text.count(old) != 1: ok = False; break
                    cur = text.replace(old, new, 1).encode("utf-8")
                states[op["index"]] = cur
            if ok:
                tracks.append({"label": "write-first", "states": states, "final": cur})
        else:
            final = seed_files.get(name)
            if final is None:
                inversion_report[name] = {"error": "no seed-archive content for edit-first file"}
            else:
                edits = [{"old": op["data"]["old_string"].replace("\r\n", "\n"),
                          "new": op["data"]["new_string"].replace("\r\n", "\n")} for op in file_ops]
                # invert from the archive bytes
                results = []

                def step(content: str, idx: int):
                    if len(results) >= args.max_branch_candidates: return
                    if idx < 0:
                        results.append(content); return
                    e = edits[idx]
                    positions, start = [], 0
                    while True:
                        i = content.find(e["new"], start)
                        if i < 0: break
                        positions.append(i); start = i + 1
                    for i in positions:
                        cand = content[:i] + e["old"] + content[i + len(e["new"]):]
                        if cand.replace(e["old"], e["new"], 1) != content: continue
                        step(cand, idx - 1)

                text_final = lf(final)
                step(text_final, len(edits) - 1)
                verified = []
                for cand in results:
                    cur = cand
                    for e in edits:
                        cur = cur.replace(e["old"], e["new"], 1)
                    if cur == text_final:
                        verified.append(cand)
                for j, cand in enumerate(verified):
                    cur_bytes = cand.encode("utf-8")
                    states = {}
                    ok = True
                    for op in file_ops:
                        text = cur_bytes.decode("utf-8").replace("\r\n", "\n")
                        old = op["data"]["old_string"].replace("\r\n", "\n")
                        new = op["data"]["new_string"].replace("\r\n", "\n")
                        if op["tool"] == "Write":
                            cur_bytes = op["data"]["content"].encode("utf-8")
                        else:
                            if text.count(old) != 1: ok = False; break
                            cur_bytes = text.replace(old, new, 1).encode("utf-8")
                        states[op["index"]] = cur_bytes
                    if ok:
                        tracks.append({"label": f"inverted-{j}", "states": states, "final": cur_bytes})
                inversion_report[name] = {"edits": len(edits), "raw_candidates": len(results),
                                          "verified_tracks": len(tracks)}
        if not tracks:
            inversion_report.setdefault(name, {})["error"] = "no verified track"
        file_options[name] = tracks

    # explicit start content for edit-first tracks (needed for pre-first-op indices)
    for name, tracks in file_options.items():
        file_ops = files_of_ops[name]
        if file_ops[0]["tool"] != "Edit": continue
        for tr in tracks:
            if tr["states"]:
                first_state_idx = min(tr["states"])
                op0 = next(o for o in file_ops if o["index"] == first_state_idx)
                after = tr["states"][first_state_idx]
                text_after = after.decode("utf-8").replace("\r\n", "\n")
                new0 = op0["data"]["new_string"].replace("\r\n", "\n")
                old0 = op0["data"]["old_string"].replace("\r\n", "\n")
                tr["start"] = text_after.replace(new0, old0, 1).encode("utf-8")
            else:
                tr["start"] = None

    # ---- option sets per commit index ----
    all_names = sorted(set(base_files) | set(seed_files), key=PureWindowsPath)
    piece_cache = {}

    def piece(name: str, content):  # content None => absent
        key = (name, content)
        if key not in piece_cache:
            piece_cache[key] = b"" if content is None else name.encode("utf-8") + hashlib.sha256(content).digest()
        return piece_cache[key]

    option_tables = []
    for i in range(len(ops) + 1):
        table = {}
        for name in all_names:
            file_ops = files_of_ops.get(name)
            if not file_ops:
                if name in base_files:
                    table[name] = [base_files[name]]
                else:
                    table[name] = [None, seed_files[name]]
                continue
            tracks = file_options.get(name) or []
            opts = []
            for tr in tracks:
                states = tr["states"]
                applied = [j for j in states if j < i]
                if applied:
                    opts.append(states[max(applied)])
                elif file_ops[0]["tool"] == "Write":
                    opts.append(base_files[name] if name in base_files else None)
                else:
                    opts.append(tr.get("start"))
                    if name not in base_files:
                        opts.append(None)  # presence before its first observed edit is unknown
            if not opts: opts = [None]
            uniq = []
            for v in opts:
                if v not in uniq: uniq.append(v)
            table[name] = uniq
        option_tables.append(table)

    # ---- enumeration & matching ----
    def save_bytes(data: bytes) -> dict:
        sha = hashlib.sha256(data).hexdigest()
        target = args.output_directory / "source-bytes" / sha
        if not target.exists():
            target.parent.mkdir(exist_ok=True)
            with target.open("xb") as stream: stream.write(data)
        return reference(target)

    matches = []
    variable_names = [n for n in all_names if len(option_tables[0][n]) > 1 or any(len(option_tables[i][n]) > 1 for i in range(len(ops) + 1))]
    combo_count = 0
    for i in range(len(ops) + 1):
        table = option_tables[i]
        var = [n for n in all_names if len(table[n]) > 1]
        fixed = {n: table[n][0] for n in all_names if len(table[n]) == 1}
        base_pieces = {n: piece(n, fixed[n]) for n in fixed}
        for choice in product(*(table[n] for n in var)):
            combo_count += 1
            digest = hashlib.sha256()
            # assemble in windows order
            chosen = dict(zip(var, choice))
            for name in all_names:
                if name in fixed:
                    p = base_pieces[name]
                else:
                    p = piece(name, chosen[name])
                if p: digest.update(p)
            hexd = digest.hexdigest()
            if hexd in wanted or hexd == seed_archive_tree:
                matches.append({"index": i, "tree_sha256": hexd,
                                "is_seed_archive_tree": hexd == seed_archive_tree,
                                "matched_wanted": hexd in wanted,
                                "variable_choice": {n: (hashlib.sha256(v).hexdigest()[:12] if v else None) for n, v in zip(var, choice)},
                                "op_context": ops[i - 1]["context"] if 0 < i <= len(ops) else None,
                                "last_op_path": ops[i - 1]["path"] if 0 < i <= len(ops) else None})

    report = {"artifact": "PRECAMPAIGN_SOURCE_RECONSTRUCTION_V2", "pass": bool(matches),
              "provider_calls": 0, "historical_commands_executed": 0,
              "history_export_sha256": hashlib.sha256(args.history_export.read_bytes()).hexdigest(),
              "base_archive": reference(args.base_archive), "seed_archive": reference(args.seed_archive),
              "seed_archive_tree_sha256": seed_archive_tree,
              "inversion": inversion_report, "combo_count": combo_count,
              "matches": matches,
              "scope": "Exact per-file inversion + forward verification; trees accepted only on exact windows_snapshot_hash equality with independently recorded case source hashes or the seed archive's own tree."}
    write_new(args.output_directory / "reconstruction.json", report)
    print(json.dumps({"combo_count": combo_count, "matches": [{k: m[k] for k in ("index", "tree_sha256", "is_seed_archive_tree", "matched_wanted", "last_op_path")} for m in matches][:40], "inversion": inversion_report}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
