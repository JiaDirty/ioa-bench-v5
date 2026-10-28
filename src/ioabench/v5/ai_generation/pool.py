"""Immutable development snapshots over existing factory, family and replay contracts.

DatasetStore deliberately accepts only FROZEN data. This development namespace shares its
manifest/cases.jsonl convention without misusing that status or creating a second registry.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from ioabench.hashing import canonical_sha256
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.core.case import case_from_dict
from ioabench.v5.dynamic import family_registry
from ioabench.v5.dynamic.signature import family_digest
from ioabench.v5.evaluation import atomic_json, safe_id, writer_lock
from ioabench.v5.replay import replay_case
from .factory import decode_json, read_json, reference_findings, validate_saved_result
from .auxiliary_runtime import AuxiliaryRouter, WIRE_REQUEST_FORMAT, qualified_contracts
from .pipeline import compile_and_gate, suite_spec
from .quality import build_review_view, compile_semantic_review, dedup_features, review_prompt, validate_semantic_review

POOL_VERSION = "ioabench.v5.development-pool/1.0.2"
SPLITS = ("development", "judge-control", "calibration", "pilot", "final-hidden")
LAYERS = ("STRUCTURALLY_VALIDATED", "MACHINE_QUALIFIED", "EMPIRICALLY_MEASURED", "SCIENTIFICALLY_FORMALLY_FROZEN")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _inside(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("evidence path is absent or escapes its root: " + str(value))
    return path


def split_report(entries: Sequence[Mapping[str, Any]], *, formal_claim: bool = False) -> dict[str, Any]:
    """Report any cross-split family/source overlap; a formal claim always fails closed."""
    conflicts = []
    for index, left in enumerate(entries):
        if left["split"] not in SPLITS:
            raise ValueError("unknown data split")
        for right in entries[index + 1:]:
            if left["split"] == right["split"]:
                continue
            families = sorted(set(left["family_keys"]) & set(right["family_keys"]))
            sources = sorted(set(left["source_keys"]) & set(right["source_keys"]))
            if families or sources:
                conflicts.append({"entries": [left["entry_id"], right["entry_id"]],
                    "splits": [left["split"], right["split"]], "shared_family_keys": families,
                    "shared_source_keys": sources})
    if formal_claim:
        raise ValueError("formal claim refused: " + ("family/source split conflict" if conflicts else
            "development pool has no authorized scientific freeze contract"))
    return {"status": "CONFLICT" if conflicts else "DISJOINT_WITHIN_DECLARED_SCOPE", "conflicts": conflicts,
            "formal_eligible": False, "scope": "declared entries, pinned existing family registry and source evidence only"}


def _machine_review(root, directory, assignment, cases, blueprint, registry_path, capture):
    review, view = read_json(directory / "REVIEW.json"), read_json(directory / "REVIEW_INPUT.json")
    expected = build_review_view(blueprint, *cases)
    request, response = read_json(directory / "AUDITOR_REQUEST.json"), read_json(directory / "AUDITOR_RESPONSE.json")
    if (view.get("paired_cases") != expected["paired_cases"] or view.get("blueprint") != blueprint
            or review.get("verdict") != "PASS" or validate_semantic_review(review, view)
            or request.get("messages") != review_prompt(view)
            or response.get("request_sha256") != canonical_sha256(request)
            or compile_semantic_review(decode_json(response.get("text")), view) != review):
        raise ValueError("machine-qualified label lacks an exact independent semantic review")
    qualification = assignment.get("auditor_qualification")
    if not qualification:
        return None
    if set(qualification) != {"preflight", "judge_controls"}:
        raise ValueError("auditor qualification needs exact preflight and judge_controls evidence")
    preflight, gold = ((root / qualification[key]).resolve() for key in ("preflight", "judge_controls"))
    for base, index in ((preflight, "SHA256SUMS.json"), (gold, "CONTROL_RESULT.json")):
        envelope = json.loads(capture(base / index))
        for name in envelope.get("files", envelope.get("evidence_sha256", {})):
            capture(_inside(base, name))
    model_id = response.get("resolved_model_id") or response.get("model_id")
    parameters = response.get("actual_parameters", request["parameters"])
    catalog, contracts, _ = qualified_contracts(preflight, workspace=root, role="INDEPENDENT_AUDITOR",
        model_ids=[model_id], gold={model_id: gold})
    contract = contracts[0]
    capture(Path(contract.preflight_evidence))
    capture(Path(contract.preflight_evidence).parent / "REQUEST_BINDING.json")
    from .model_routing import served_catalog_entry
    served = served_catalog_entry(response.get("provider_metadata", {}), catalog)
    generators = [read_json(path) for path in directory.glob("GENERATOR*RESPONSE.json")]
    generator_developers = {str(item.get("developer_id")) for item in generators}
    if (not served or (served.get("model_id") or served.get("id")) != model_id
            or parameters != contract.parameters or str(contract.entry["developer_id"]) in generator_developers):
        raise ValueError("review identity, parameters or generator/auditor separation differs from qualification")
    families, sources = set(), set()
    controls = read_json(gold / "GOLD_CONTROLS.json")
    by_id = {control["id"]: control for control in controls}
    for control in controls:
        sources.add(canonical_sha256(control["view"]["blueprint"]))
        sources.update(canonical_sha256(raw) for raw in control["view"]["paired_cases"])
        source = control
        if control.get("control_input_kind") == "MUTATED_REVIEW_INPUT":
            source = by_id[control["source_control_id"]]
            if (canonical_sha256(source["view"]) != control["source_input_sha256"]
                    or canonical_sha256(source["view"]["paired_cases"]) != control["source_paired_cases_sha256"]
                    or source["hard_gate_sha256"] != control["source_hard_gate_sha256"]):
                raise ValueError("mutated judge control source binding changed")
        # Planted invalid worlds inherit source-family isolation, not executable status.
        for raw in source["view"]["paired_cases"]:
            suite = raw["suite_id"].split("-")[0]
            digest = family_digest(raw)
            spec = suite_spec(suite, typed=True)
            classification = family_registry.classify(registry_path, suite_id=suite, digest=digest)
            families.update(suite + ":id:" + family for family in classification.get("matching_families", []))
            families.update((suite + ":legacy:" + digest,
                suite + ":runtime:" + canonical_sha256(dedup_features(raw, scenario=spec.scenario_factory())["structure"])))
            sources.add(canonical_sha256(raw))
    return {"status": "ENGINEERING_CONTROLS_PASS", "model_id": model_id,
            "preflight": preflight.relative_to(root).as_posix(), "judge_controls": gold.relative_to(root).as_posix(),
            "split_membership": {"entry_id": "judge-controls:" + sha256(capture(gold / "CONTROL_RESULT.json")).hexdigest(),
                "split": "judge-control", "family_keys": sorted(families), "source_keys": sorted(sources)},
            "scope": "Existing exact-ID preflight and fixed engineering controls; no scientific reliability claim"}


def _strict_replay(row, case, model, source, journal_root, capture):
    if row.get("case_sha256") != case.content_sha256() or row.get("model_id") != model["profile"]["model_id"]:
        raise ValueError("execution case/model identity differs from its contract")
    journal = _inside(journal_root, row["attempt_journal"]["path"])
    journal_content = capture(journal)
    if sha256(journal_content).hexdigest() != row["attempt_journal"]["sha256"]:
        raise ValueError("execution attempt journal changed")
    entries = [json.loads(line) for line in journal_content.decode("utf-8").splitlines() if line.strip()]
    if (not entries or entries[0] != {"kind": "attempt", "run_id": row["run_id"], "suite_id": case.suite_id,
            "case_id": case.case_id, "attempt_no": row["attempt_no"]}
            or len(entries) - 1 != row["model_calls"]):
        raise ValueError("execution journal identity or model-call denominator changed")
    # A temporary replay projection preserves every historical input and attempt byte.
    with tempfile.TemporaryDirectory(prefix="ioa-pool-replay-") as temporary:
        root = Path(temporary)
        destination = root / row["attempt_journal"]["path"]
        destination.parent.mkdir(parents=True)
        destination.write_bytes(journal_content)
        run = root / "artifacts/v5/evaluations" / safe_id(row["run_id"])
        atomic_json(run / "manifest.json", {"source_sha256": source, **model,
            "cases": [{"case_id": case.case_id, "case_sha256": case.content_sha256()}]})
        for name, value in (("cases.jsonl", case.as_dict()), ("results.jsonl", row)):
            (run / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        report = replay_case(root, row["run_id"], case.case_id)
    if not report["passed"]:
        raise ValueError("retained execution failed strict replay")
    return report


def _measurements(directory, cases, source, capture):
    contract = json.loads(capture(directory / "CALIBRATION_CONTRACT.json"))
    rows = json.loads(capture(directory / "RESULTS.json"))
    capture(directory / "CALIBRATION_REPORT.json")
    selected = [case_from_dict(raw, allow_dynamic=True) for raw in json.loads(capture(directory / "PAIRS.json"))]
    if (contract.get("runtime_source_sha256") != source or contract.get("formal_SUT_used") is not False
            or [case.content_sha256() for case in selected] != contract["selected_case_sha256"]):
        raise ValueError("measurement panel source, selection or auxiliary-role contract differs")
    if (directory / "STOP_REPORT.json").exists():
        stop = json.loads(capture(directory / "STOP_REPORT.json"))
        for name, digest in {**stop["evidence_sha256"], **stop["settled_outputs_sha256"]}.items():
            if sha256(capture(_inside(directory, name))).hexdigest() != digest:
                raise ValueError("stopped measurement evidence changed")
    profiles = {item["profile"]["model_id"]: item for item in contract["models"]}
    expected = {f"{model}-r{repetition}-{case.suite_id}-{case.arm.lower()}": (case, profiles[model])
                for model in profiles for repetition in range(1, contract["repetitions"] + 1) for case in selected}
    if len(rows) != len(expected) or len({row["run_id"] for row in rows}) != len(expected):
        raise ValueError("measurement panel denominator or unique identities changed")
    measured = {}
    wanted = {case.content_sha256() for case in cases}
    for row in rows:
        case, model = expected[row["run_id"]]
        if (row.get("case_sha256") != case.content_sha256() or row.get("case_id") != case.case_id
                or row.get("arm") != case.arm or row.get("model_id") != model["profile"]["model_id"]):
            raise ValueError("measurement row differs from its fixed selection")
        if model["profile"].get("role") != "CALIBRATOR" or model["profile"]["model_id"].casefold().startswith("deepseek"):
            raise ValueError("formal tested family or non-calibrator role in development measurement")
        if case.content_sha256() not in wanted or row.get("status") != "COMPLETED" or not row.get("scientifically_eligible"):
            continue
        if not row.get("score") or "trace" not in row:
            raise ValueError("measured label requires actual complete scored behavior")
        io = directory / "episodes" / safe_id(row["run_id"]) / "model_io"
        ledger = json.loads("[" + ",".join(capture(io / "AIHUBMIX_ATTEMPTS.jsonl").decode("utf-8").splitlines()) + "]")
        AuxiliaryRouter.verify_ledger(SimpleNamespace(directory=io))
        starts, finishes, successes, counts = {}, {}, [], {}
        for event in ledger:
            if event.get("event") == "REQUEST_STARTED":
                ident, request_id = event["attempt_id"], safe_id(event["request_id"])
                if ident in starts or len(starts) != len(finishes):
                    raise ValueError("measurement repeated a duplicate or unresolved request")
                binding = json.loads(capture(_inside(io, request_id + "/REQUEST_BINDING.json")))
                bound = binding["binding"]
                wire = {**bound["request"], "parameters": model["parameters"],
                    "role_metadata": {**bound["request"].get("role_metadata", {}), "role": "CALIBRATOR", "attempt_id": ident}}
                wire_format = event.get("wire_request_format")
                if wire_format == WIRE_REQUEST_FORMAT:
                    evidence = Path(event["stream_evidence_path"])
                    if (evidence.parent.name != request_id
                            or evidence.name != f"attempt-{counts.get(request_id, 0) + 1:03d}.sse"):
                        raise ValueError("stream evidence path does not belong to its request attempt")
                    wire["role_metadata"]["stream_evidence_path"] = event["stream_evidence_path"]
                elif wire_format is not None:
                    raise ValueError("unsupported router wire-request format")
                if (canonical_sha256(bound) != binding["sha256"] or bound["role"] != "CALIBRATOR"
                        or bound["contracts"] != [model] or canonical_sha256(wire) != event["request_sha256"]
                        or event["requested_model_id"] != row["model_id"] or event["role"] != "CALIBRATOR"
                        or event["actual_parameters"] != model["parameters"]):
                    raise ValueError("measurement request differs from its fixed model/parameters/wire binding")
                starts[ident] = event
                counts[request_id] = counts.get(request_id, 0) + 1
            elif event.get("event") == "REQUEST_FINISHED":
                ident = event["attempt_id"]
                start = starts.get(ident)
                if (start is None or ident in finishes or any(start.get(key) != event.get(key)
                        for key in ("request_id", "requested_model_id", "role", "request_sha256", "actual_parameters",
                                    "wire_request_format", "stream_evidence_path"))
                        or event["status"] not in {"SUCCEEDED", "FAILED"}):
                    raise ValueError("measurement completion lacks a unique matching resolved request")
                finishes[ident] = event
                if event["status"] == "SUCCEEDED":
                    successes.append(event)
        if (not starts or len(starts) != len(finishes) or max(counts.values()) > 3
                or len(counts) != len(successes) or len(successes) != row["model_calls"]
                or len(row["trace"]["records"]) != len(successes)):
            raise ValueError("measurement attempts do not match bounded completed responses")
        for event, record in zip(successes, row["trace"]["records"]):
            binding = json.loads(capture(_inside(io, safe_id(event["request_id"]) + "/REQUEST_BINDING.json")))
            saved = json.loads(capture(_inside(io, safe_id(event["request_id"]) + "/RESPONSE.json")))
            if (event["requested_model_id"] != row["model_id"] or event["served_model_id"] != row["model_id"]
                    or event["role"] != "CALIBRATOR" or event["actual_parameters"] != model["parameters"]
                    or canonical_sha256(binding["binding"]) != binding["sha256"]
                    or saved["binding_sha256"] != binding["sha256"] or saved["response"] != event["response"]
                    or canonical_sha256(saved["response"]) != saved["response_sha256"]
                    or canonical_sha256(binding["binding"]["request"]) != record["request_sha256"]
                    or any(canonical_sha256(value) != canonical_sha256(event["response"].get(key))
                           for key, value in record["response"].items() if key != "elapsed_seconds")):
                raise ValueError("measurement routing identity, parameters or response binding changed")
        replay = _strict_replay(row, case, {key: model[key] for key in ("profile", "parameters")}, source,
                                directory / "replay", capture)
        measured.setdefault(case.content_sha256(), []).append({"run_id": row["run_id"], "model_id": row["model_id"],
            "score": row["score"], "outcome": row["outcome"], "strict_replay": replay,
            "empirical_label": "UNCALIBRATED", "scope": "exploratory measurement; no numerical difficulty label"})
    return measured, wanted & {case.content_sha256() for case in selected}


def build_pool(root: Path, output: Path, assignments: Sequence[Mapping[str, Any]], *,
               registry_path: Path, expected_source_sha256: str, formal_claim: bool = False) -> dict[str, Any]:
    """Snapshot existing candidates; never register families, call models or freeze formal data."""
    root, output, registry_path = Path(root).resolve(), Path(output).resolve(), Path(registry_path).resolve()
    if not assignments or source_tree_hash(root) != expected_source_sha256:
        raise ValueError("nonempty assignments and the pinned current runtime source are required")
    blobs, origins = {}, {}

    def capture(path):
        path = Path(path).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.is_relative_to(output):
            raise ValueError("pool input evidence is outside workspace, absent or inside its output")
        content = path.read_bytes()
        digest = sha256(content).hexdigest()
        name = path.relative_to(root).as_posix()
        if name in origins and origins[name] != digest:
            raise ValueError("pool source changed while reading")
        origins[name], blobs["evidence/" + digest] = digest, content
        return content

    capture(registry_path)
    entries, stored_cases, rejected = [], {}, []
    for assignment in sorted(assignments, key=lambda item: (item["directory"], item["split"])):
        if set(assignment) - {"directory", "split", "calibration", "source_files", "auditor_qualification"} or assignment["split"] not in SPLITS:
            raise ValueError("unknown pool assignment field or split")
        directory = (root / assignment["directory"]).resolve()
        if any(entry["directory"] == directory.relative_to(root).as_posix() for entry in entries):
            raise ValueError("candidate has multiple split assignments")
        result = json.loads(capture(directory / "RESULT.json"))
        validate_saved_result(directory, result)
        if (directory / "TERMINAL.json").is_file():
            capture(directory / "TERMINAL.json")
        for name in result["evidence_sha256"]:
            capture(_inside(directory, name))
        manifest = read_json(directory / "MANIFEST.json")
        if manifest["source_sha256"] != expected_source_sha256:
            raise ValueError("candidate was not executed under the pinned current source")
        ident = directory.relative_to(root).as_posix()
        entry = {"entry_id": canonical_sha256({"directory": ident, "result_sha256": origins[ident + "/RESULT.json"]}),
            "directory": ident, "split": assignment["split"], "factory_status": result["status"],
            "family_keys": [], "source_keys": [], "case_sha256": [], "layers": [], "findings": []}
        sources = {manifest.get(key) for key in ("baseline_sha256", "proposal_sha256") if manifest.get(key)}
        for name in ("BLUEPRINT.json", "GENERATOR_RESPONSE.json", "PROGRAM_PROPOSAL.json"):
            if (directory / name).is_file():
                sources.add(sha256(capture(directory / name)).hexdigest())
        if (directory / "BLUEPRINT.json").is_file():
            sources.add(canonical_sha256(read_json(directory / "BLUEPRINT.json")))
        for name in assignment.get("source_files", []):
            sources.add(sha256(capture(_inside(root, name))).hexdigest())
        entry["source_keys"] = sorted(sources)
        structural = all((directory / name).is_file() for name in ("PAIR.json", "BLUEPRINT.json", "HARD_GATE.json", "REFERENCE_RESULTS.json"))
        if structural and read_json(directory / "HARD_GATE.json").get("passed") is True:
            cases = [case_from_dict(raw, allow_dynamic=True) for raw in read_json(directory / "PAIR.json")]
            if len(cases) != 2 or [case.arm for case in cases] != ["CONTROL", "RISK"]:
                raise ValueError("pool candidate needs one ordered CONTROL/RISK pair")
            spec = suite_spec(cases[0].suite_id, typed=True)
            if spec.adapter.adapter_version != manifest["adapter_version"]:
                spec = suite_spec(cases[0].suite_id)
            if spec.adapter.adapter_version != manifest["adapter_version"]:
                raise ValueError("candidate compiler differs from the current pinned contract")
            compiled = compile_and_gate(spec, read_json(directory / "BLUEPRINT.json"), seed=manifest["seed"])
            if canonical_sha256([compiled[arm].as_dict() for arm in ("control", "risk")]) != canonical_sha256([case.as_dict() for case in cases]):
                raise ValueError("persisted pair differs from programmatic compilation")
            reference_rows = read_json(directory / "REFERENCE_RESULTS.json")
            if reference_findings(spec, reference_rows, {case.arm: case for case in cases}):
                raise ValueError("retained reference execution matrix is invalid")
            for row in reference_rows:
                case = next(case for case in cases if case.arm == row["arm"])
                model = {"profile": {"provider": "scripted", "model_id": "reference-policy", "capabilities": {},
                                     "default_parameters": {}, "role": "REFERENCE_POLICY"}, "parameters": {"temperature": 0.0}}
                _strict_replay(row, case, model, expected_source_sha256, directory / "replay", capture)
            entry["layers"].append(LAYERS[0])
            machine = result["status"] == "MACHINE_ACCEPTED"
            if machine:
                qualification = _machine_review(root, directory, assignment, cases, read_json(directory / "BLUEPRINT.json"), registry_path, capture)
                entry["auditor_qualification"] = qualification or {"status": "NOT_RUN_NO_BOUND_PREFLIGHT_AND_CONTROLS"}
                machine = qualification is not None
                if machine:
                    entry["layers"].append(LAYERS[1])
                else:
                    entry["findings"].append("Auditor exact-ID preflight and fixed controls not bound; machine layer NOT_RUN")
            measured, selected_hashes = (_measurements((root / assignment["calibration"]).resolve(), cases,
                expected_source_sha256, capture) if assignment.get("calibration") else ({}, set()))
            if selected_hashes:
                entry.update(measurement_split="calibration", measurement_directory=assignment["calibration"],
                             measurement_selection_sha256=sorted(selected_hashes))
            if assignment.get("calibration") and not measured:
                entry["findings"].append("No complete eligible measurement of these exact case hashes; empirical layer NOT_RUN")
            for case in cases:
                digest = case.content_sha256()
                features = dedup_features(case, scenario=spec.scenario_factory())
                classification = family_registry.classify(registry_path, suite_id=case.suite_id.split("-")[0],
                                                          digest=family_digest(case.as_dict()))
                family_ids = {case.family_id, *classification.get("matching_families", [])}
                entry["family_keys"] += [case.suite_id.split("-")[0] + ":id:" + family for family in sorted(family_ids)]
                entry["family_keys"] += [case.suite_id.split("-")[0] + ":legacy:" + family_digest(case.as_dict()),
                                         case.suite_id.split("-")[0] + ":runtime:" + canonical_sha256(features["structure"])]
                entry["source_keys"].append(digest)
                entry["source_keys"].append(canonical_sha256(build_review_view({}, case, case)["paired_cases"][0]))
                entry["case_sha256"].append(digest)
                stored_cases[digest] = case.as_dict()
                entry.setdefault("case_layers", {})[digest] = [*entry["layers"], *([LAYERS[2]] if machine and digest in measured else [])]
                entry.setdefault("family_registry_classification", {})[digest] = classification
            if measured:
                entry["measurements"] = measured
                if machine:
                    entry["layers"].append(LAYERS[2])
        else:
            entry["findings"].append("No complete passing compile/gate/reference evidence; retained without promotion")
            rejected.append({"entry_id": entry["entry_id"], "status": result["status"], "findings": result.get("findings", [])})
        entry["family_keys"], entry["source_keys"] = sorted(set(entry["family_keys"])), sorted(set(entry["source_keys"]))
        entries.append(entry)
    memberships = entries + [{**entry, "entry_id": entry["entry_id"] + ":measurement-selection", "split": "calibration"}
                             for entry in entries if entry.get("measurement_split") == "calibration"]
    memberships += list({entry["auditor_qualification"]["split_membership"]["entry_id"]:
                         entry["auditor_qualification"]["split_membership"] for entry in entries
                         if entry.get("auditor_qualification", {}).get("split_membership")}.values())
    splits = split_report(memberships, formal_claim=formal_claim)
    files = {**blobs, "entries.json": _json_bytes(entries), "splits.json": _json_bytes(splits),
        "cases.jsonl": "".join(json.dumps(stored_cases[key], ensure_ascii=False, sort_keys=True) + "\n"
                                 for key in sorted(stored_cases)).encode("utf-8"), "rejected.json": _json_bytes(rejected)}
    manifest = {"pool_version": POOL_VERSION, "status": "IMMUTABLE_DEVELOPMENT_SNAPSHOT",
        "runtime_source_sha256": expected_source_sha256, "assignments": list(assignments),
        "origin_sha256": origins, "family_registry": registry_path.relative_to(root).as_posix(),
        "split_status": splits["status"], "entries": len(entries), "cases": len(stored_cases),
        "layer_case_counts": {layer: len({digest for entry in entries for digest, layers in entry.get("case_layers", {}).items()
                                         if layer in layers}) for layer in LAYERS},
        "scientific_freeze": "NOT_RUN_NO_AUTHORIZED_FREEZE_CONTRACT",
        "formal_accepted": False, "provider_calls": 0, "files_sha256": {name: sha256(content).hexdigest() for name, content in files.items()}}
    manifest["content_sha256"] = canonical_sha256(manifest)
    if source_tree_hash(root) != expected_source_sha256 or any(sha256((root / name).read_bytes()).hexdigest() != digest
                                                            for name, digest in origins.items()):
        raise ValueError("pool input or runtime source changed during verification")
    with writer_lock(output.parent):
        if (output / "manifest.json").exists():
            retained = verify_pool(output)
            if retained != manifest:
                raise ValueError("immutable pool request or input evidence changed; use a new output")
            return retained
        output.mkdir(parents=True, exist_ok=True)
        for name, content in {**files, "manifest.json": _json_bytes(manifest)}.items():
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.read_bytes() != content:
                    raise ValueError("partial immutable pool output changed")
            else:
                with path.open("xb") as stream:
                    stream.write(content)
    return verify_pool(output)


def verify_pool(output: Path) -> dict[str, Any]:
    output = Path(output).resolve()
    manifest = read_json(output / "manifest.json")
    if canonical_sha256({key: value for key, value in manifest.items() if key != "content_sha256"}) != manifest["content_sha256"]:
        raise ValueError("pool manifest content hash changed")
    expected = {"manifest.json", *manifest["files_sha256"]}
    if {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()} != expected:
        raise ValueError("pool evidence inventory changed")
    for name, digest in manifest["files_sha256"].items():
        if sha256(_inside(output, name).read_bytes()).hexdigest() != digest:
            raise ValueError("pool bound evidence changed: " + name)
    if manifest["formal_accepted"] is not False or manifest["layer_case_counts"][LAYERS[3]] != 0:
        raise ValueError("development pool cannot promote a scientific/formal freeze")
    return manifest
