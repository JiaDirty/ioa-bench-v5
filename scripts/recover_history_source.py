"""Recover source bytes from literal edit data; never execute historical code."""
from __future__ import annotations

import argparse
import ast
import hashlib
from itertools import product
import json
import math
from pathlib import Path, PureWindowsPath
import re
from zipfile import ZipFile

from scientific_closure import ROOT, windows_snapshot_hash, read_json, reference, write_new


class SourcePath(str):
    pass


def source_path(value: str) -> SourcePath:
    value = value.replace("\\", "/")
    if PureWindowsPath(value).is_absolute():
        prefix = str(ROOT).replace("\\", "/").rstrip("/") + "/"
        if not value.casefold().startswith(prefix.casefold()):
            raise ValueError("path outside workspace")
        value = value[len(prefix):]
    if ":" in value or any(p in {"", ".", ".."} for p in value.split("/")) or not value.startswith(("src/", "contracts/", "config/")):
        raise ValueError("not a scientific source path")
    return SourcePath(value)


def literal_value(node, values, files):
    """An allowlist of data expressions; calls outside it are rejected."""
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Name): return values[node.id]
    if isinstance(node, (ast.List, ast.Tuple)): return [literal_value(x, values, files) for x in node.elts]
    if isinstance(node, ast.Dict): return {literal_value(k, values, files): literal_value(v, values, files) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal_value(node.left, values, files) + literal_value(node.right, values, files)
    if isinstance(node, ast.Call):
        args = [literal_value(x, values, files) for x in node.args]
        keywords = {k.arg: literal_value(k.value, values, files) for k in node.keywords}
        if keywords and (not isinstance(node.func, ast.Attribute) or node.func.attr != "read_text" or keywords != {"encoding": "utf-8"}):
            raise ValueError("unsupported call keywords")
        if isinstance(node.func, ast.Name) and node.func.id == "Path" and len(args) == 1:
            return source_path(args[0])
        if isinstance(node.func, ast.Attribute):
            receiver = literal_value(node.func.value, values, files)
            method = node.func.attr
            if isinstance(receiver, SourcePath) and method == "read_text":
                return files[str(receiver)].decode("utf-8").replace("\r\n", "\n")
            if type(receiver) is str and method in {"replace", "rstrip", "strip", "lstrip", "join"}:
                return getattr(receiver, method)(*args)
    raise ValueError("expression is outside the literal reconstruction subset")


def python_writes(source: str, files: dict, commit):
    values, skipped = {}, 0
    for statement in ast.parse(source).body:
        try:
            if isinstance(statement, ast.Assign):
                value = literal_value(statement.value, values, files)
                for target in statement.targets:
                    if isinstance(target, ast.Name): values[target.id] = value
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == "write_text":
                    keywords = {k.arg: literal_value(k.value, values, files) for k in call.keywords}
                    if len(call.args) != 1 or keywords not in ({}, {"encoding": "utf-8"}): raise ValueError("unsupported write options")
                    target = literal_value(call.func.value, values, files)
                    content = literal_value(call.args[0], values, files)
                    if not isinstance(target, SourcePath) or not isinstance(content, str): raise ValueError("nonliteral write")
                    commit(str(target), content.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
                else: raise ValueError("unsupported expression")
            elif not isinstance(statement, (ast.Import, ast.ImportFrom, ast.Pass)):
                raise ValueError("unsupported statement")
        except (ValueError, KeyError, TypeError, AttributeError):
            # Unresolved assignments never reuse an earlier stale variable value.
            for target in ast.walk(statement):
                if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store): values.pop(target.id, None)
            skipped += 1
    return skipped


def combine_variants(initial, variants, wanted):
    """Search preserved byte choices; a recorded hash is the only acceptance rule."""
    trials = math.prod(len(v) for v in variants.values())
    if trials > 200_000: raise ValueError("review reconstruction scope before expanding it")
    names = [n for d in ("src", "contracts", "config") for n in sorted(
        (n for n in initial.keys() | variants.keys() if n.startswith(d + "/")), key=PureWindowsPath)]
    pieces, variables, fixed = [], [], b""
    for name in names:
        def piece(value):
            return name.encode() + hashlib.sha256(value).digest() if value is not None else b""
        if name in variants:
            pieces.extend([(fixed,), tuple(piece(v) for v in variants[name])])
            variables.append(name); fixed = b""
        else: fixed += piece(initial[name])
    pieces.append((fixed,))
    found = {}
    for choice in product(*(range(len(variants[n])) for n in variables)):
        payload = b"".join(p[choice[(i-1)//2]] if i % 2 else p[0] for i,p in enumerate(pieces))
        digest = hashlib.sha256(payload).hexdigest()
        if digest not in wanted: continue
        files = dict(initial)
        for name, option in zip(variables, choice):
            data = variants[name][option]
            if data is None: files.pop(name, None)
            else: files[name] = data
        assert windows_snapshot_hash(files) == digest
        found[digest] = files
    return trials, found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-export", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    args.output_directory = args.output_directory.resolve()
    if not args.output_directory.is_relative_to(ROOT):
        raise ValueError("recovery artifacts must stay in this workspace")
    args.output_directory.mkdir(parents=True, exist_ok=False)
    old_archive = ROOT / "archive/deliveries/IoA-Bench-current-workspace-handoff-20260929-latest.zip"
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
    impact = read_json(ROOT / "artifacts/gates/V32_S1_POLICY_IMPACT_v2.json")
    horizon = max(row["tool_time"]["end"] for row in impact["historical_observations"]["observations"] if row["suite"] == "T323")
    variants = {}
    for row in mutations:
        if row["tool_end_unix_ms"] is None or row["tool_end_unix_ms"] > horizon: continue
        name = row["path"]
        values = variants.setdefault(name, [initial.get(name)])
        data = (ROOT / row["content"]["path"]).read_bytes()
        if data not in values: values.append(data)
    variants.setdefault("config/synthetic_human.json", [None])
    for name, values in variants.items():
        data = (ROOT / name).read_bytes() if (ROOT / name).is_file() else None
        if data not in values: values.append(data)
    trials, matches = combine_variants(initial, variants, wanted - recovered.keys())
    for digest, snapshot in matches.items():
        save_match(digest, snapshot, {"method": "preserved_byte_combinations", "variant_paths": sorted(variants)})
    report = {"artifact": "LITERAL_HISTORY_SOURCE_RECOVERY", "pass": True, "provider_calls": 0,
              "historical_commands_executed": 0, "history_export_sha256": hashlib.sha256(args.history_export.read_bytes()).hexdigest(),
              "base_archive": reference(old_archive), "mutations": mutations, "recovered": recovered, "ignored": ignored,
              "combination_trials": trials, "variant_counts": {k: len(v) for k, v in variants.items()},
              "newly_resolved_cases": sum(g["case_count"] for row in prior["suites"] for g in row["groups"] if g["recorded_source_sha256"] in recovered),
              "scope": "Literal static reconstruction only. Incomplete statement handling is explicit; only exact matches to independently recorded source hashes count as recovered."}
    write_new(args.output_directory / "recovery.json", report)
    print(json.dumps({"source_mutations": len(mutations), "recovered_hashes": list(recovered), "newly_resolved_cases": report["newly_resolved_cases"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
