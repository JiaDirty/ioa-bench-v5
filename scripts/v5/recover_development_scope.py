"""Recover omitted T322 full-index artifacts from frozen local inputs; never resend."""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
VERSION = "ioabench.v5.t322-full-index-recovery/1.0.0"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def child(directory, value):
    path = (directory / value).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError("recovery input escaped its bound directory")
    return path


def single(paths, label):
    values = list(paths)
    if len(values) != 1:
        raise ValueError("exactly one frozen " + label + " is required; select it explicitly")
    return values[0]


def frozen_extend(path, root, case_from_dict, suite_spec, dedup_features):
    """Load only the recorded pure history helper, never its CLI or provider setup."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = single((item for item in tree.body if isinstance(item, ast.FunctionDef)
                   and item.name == "extend_history"), "extend_history function")
    if node.decorator_list:
        raise ValueError("unexpected frozen history helper decorators")
    namespace = {"ROOT": root, "read": read, "sha": sha, "case_from_dict": case_from_dict,
                 "suite_spec": suite_spec, "dedup_features": dedup_features}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["extend_history"]


def recover(out, root, *, plan_path=None, binding_path=None, result_path=None):
    out, root = Path(out).resolve(), Path(root).resolve()
    if not out.is_relative_to(root / "artifacts/v5/data_factory/dev_auto_audit"):
        raise ValueError("recovery requires the isolated development evidence directory")
    destination = child(out, result_path) if result_path else out / "T322_FULL_INDEX_RECOVERY_V1.json"
    if destination.exists():
        raise ValueError("recovery receipt is immutable; select a new --result")
    binding_path = child(out, binding_path) if binding_path else single(
        sorted(out.glob("GENERATE_SOURCE_BINDING-*.json")), "generate source binding")
    binding = read(binding_path)
    if binding.get("phase") != "generate":
        raise ValueError("source binding is not a generation execution")
    runtime, script_hash = binding["runtime_sha256"], binding["script_sha256"]
    snapshot = child(out, "source_revisions/" + runtime)
    script = child(out, "execution_scripts/" + script_hash + ".py")
    if sha(script) != script_hash:
        raise ValueError("frozen runner does not match the generation source binding")
    sys.path.insert(0, str(snapshot / "src"))
    from ioabench.hashing import canonical_sha256
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5.ai_generation import quality, t322_history
    from ioabench.v5.ai_generation.direct_deepseek import candidate_result
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.core.case import case_from_dict
    from ioabench.v5.evaluation import atomic_json, writer_lock
    from verify_development_factory import ledger_inventory, no_network
    if (source_tree_hash(snapshot) != runtime or any(not Path(module.__file__).resolve().is_relative_to(snapshot)
            for module in (quality, t322_history))):
        raise ValueError("recovery must run in a fresh process using the exact frozen runtime")
    history_binding_path = out / ("HISTORY_BINDING-" + runtime[:12] + ".json")
    history_binding = read(history_binding_path)
    base_path = child(out, history_binding["history_path"])
    if base_path != out / "history" / (runtime + ".json") or sha(base_path) != history_binding["sha256"]:
        raise ValueError("frozen history base does not match its binding")
    if plan_path is None:
        plan_path = single((path for path in sorted((out / "plans").glob("*.json"))
                            if isinstance(read(path).get("tasks"), list)), "task plan")
    else:
        plan_path = child(out, plan_path)
    plan = read(plan_path)
    tasks = plan["tasks"]
    if not tasks or tasks[0]["suite"] == "T322" or len({task["id"] for task in tasks}) != len(tasks):
        raise ValueError("recovery requires the inspected unique plan beginning with full-history work")
    scopes = {path.name: path for path in sorted(out.glob("T322_VERSION_SCOPE-*.json"))}
    if not scopes:
        raise ValueError("there is no persisted T322 scope report to recover")
    inputs = {}

    def bind(path):
        path = Path(path).resolve()
        if not path.is_relative_to(root):
            raise ValueError("recovery input is outside --root")
        inputs[path.relative_to(root).as_posix()] = sha(path)

    for path in (binding_path, script, history_binding_path, base_path, plan_path):
        bind(path)
    extend = frozen_extend(script, root, case_from_dict, suite_spec, quality.dedup_features)
    recovered, steps, seen = [], [], set()
    with writer_lock(root / "artifacts/v5/data_factory"), writer_lock(out), no_network() as guard:
        ledger_before = ledger_inventory(out)
        index = read(base_path)
        for name, digest in index["source_sha256"].items():
            path = child(root, name)
            if not path.is_file() or sha(path) != digest:
                raise ValueError("frozen historical source binding changed")
        if index["projection_source_sha256"] != runtime:
            raise ValueError("history projection was not made by the recorded runtime")
        initial_hash = canonical_sha256(index)
        first_manifest = read(child(out, "candidates/" + tasks[0]["id"] + "/MANIFEST.json"))
        initial_overlay = out / "history" / ("overlay-" + initial_hash + ".json")
        if first_manifest["history_sha256"] != initial_hash or read(initial_overlay) != index:
            raise ValueError("startup retained-history state is ambiguous; do not guess an initial index")
        bind(initial_overlay)
        for ordinal, task in enumerate(tasks):
            source = child(out, "candidates/" + task["id"])
            if not all((source / name).is_file() for name in ("MANIFEST.json", "RESULT.json", "TERMINAL.json")):
                raise ValueError("recovery requires complete sealed candidate inputs before every matched scope")
            manifest = read(source / "MANIFEST.json")
            if manifest["source_sha256"] != runtime or manifest["task"] != task:
                raise ValueError("candidate belongs to a different runtime or task plan")
            candidate_result(source)
            for name in ("MANIFEST.json", "RESULT.json", "TERMINAL.json", "PAIR.json", "BEHAVIORAL_PROBES.json"):
                if (source / name).exists():
                    bind(source / name)
            before = canonical_sha256(index)
            if task["suite"] == "T322":
                selected, expected_scope = t322_history.version_scoped_index(index)
                scope_name = "T322_VERSION_SCOPE-" + before + ".json"
                if scope_name not in scopes or read(scopes[scope_name]) != expected_scope:
                    raise ValueError("reconstructed full index does not match the recorded T322 scope")
                selected_hash = canonical_sha256(selected)
                selected_path = out / "history" / ("overlay-" + selected_hash + ".json")
                if manifest["history_sha256"] != selected_hash or read(selected_path) != selected:
                    raise ValueError("reconstructed scoped index differs from the manifest or frozen overlay")
                bind(scopes[scope_name])
                bind(selected_path)
                seen.add(scope_name)
                recovered.append({"task_id": task["id"], "full_history_index_sha256": before,
                    "scope_report": scopes[scope_name].relative_to(root).as_posix(),
                    "scoped_index_sha256": selected_hash, "value": deepcopy(index)})
            elif manifest["history_sha256"] != before:
                raise ValueError("reconstructed full-history task input differs from its manifest")
            extend(index, source)
            steps.append({"ordinal": ordinal, "task_id": task["id"], "before_sha256": before,
                          "after_sha256": canonical_sha256(index), "candidate_status": read(source / "RESULT.json")["status"]})
            if seen == set(scopes):
                break
        if seen != set(scopes):
            raise ValueError("one or more recorded T322 scopes cannot be reconstructed")
        if guard["provider_http_or_external_network_attempts"] or ledger_inventory(out) != ledger_before:
            raise ValueError("scope recovery attempted network access or changed a request ledger")
        for name, digest in inputs.items():
            if sha(root / name) != digest:
                raise ValueError("bound recovery input changed during reconstruction")
        for row in recovered:
            path = out / "history" / ("overlay-" + row["full_history_index_sha256"] + ".json")
            if path.exists() and read(path) != row["value"]:
                raise ValueError("existing full-index artifact differs; it will not be overwritten")
        outputs = {}
        for row in recovered:
            digest, value = row["full_history_index_sha256"], row.pop("value")
            path = out / "history" / ("overlay-" + digest + ".json")
            relative = path.relative_to(root).as_posix()
            if relative in outputs:
                continue
            existed = path.exists()
            if existed and read(path) != value:
                raise ValueError("existing full-index artifact differs; it will not be overwritten")
            if not existed:
                atomic_json(path, value)
            if canonical_sha256(read(path)) != digest:
                raise ValueError("recovered full-index artifact hash differs")
            outputs[relative] = {"sha256": sha(path), "canonical_sha256": digest,
                                 "existed_before_recovery": existed}
        result = {"version": VERSION, "status": "PASS", "method": "POST_RUN_DETERMINISTIC_RECONSTRUCTION",
            "original_persistence_claim": False, "provider_calls": 0, "new_generation_requests": 0,
            "runtime_sha256": runtime, "frozen_runner_sha256": script_hash, "initial_index_sha256": initial_hash,
            "bound_inputs_sha256": inputs, "base_source_bindings_verified": len(read(base_path)["source_sha256"]),
            "steps": steps, "matched_scopes": recovered, "recovered_files": outputs,
            "request_ledgers_before": ledger_before, "request_ledgers_after": ledger_inventory(out),
            "ledger_unchanged": ledger_inventory(out) == ledger_before, "network_guard": guard,
            "formal_accepted": False, "global_novelty_proven": False,
            "required_t322_pool_status": "QUARANTINED_HISTORY_INDETERMINATE",
            "limitation": "This appends a verified reconstruction after the run; it does not claim the full index was saved at request time."}
        atomic_json(destination, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--plan", type=Path, help="frozen plan inside --out")
    parser.add_argument("--binding", type=Path, help="frozen generation source binding inside --out")
    parser.add_argument("--result", type=Path, help="new immutable receipt inside --out")
    args = parser.parse_args()
    result = recover(args.out, args.root, plan_path=args.plan, binding_path=args.binding, result_path=args.result)
    print(json.dumps({key: result[key] for key in ("status", "provider_calls", "ledger_unchanged")}))


if __name__ == "__main__":
    main()
