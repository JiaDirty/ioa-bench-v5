"""Verify development seals and exact-source Replay/resume without provider access."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_ROOT = PureWindowsPath("D:/Project/ioa_codex_spec")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_child(directory, name):
    if PureWindowsPath(name).is_absolute() or ".." in PureWindowsPath(name).parts:
        raise ValueError("evidence member must be a traversal-free relative path")
    path = (Path(directory) / name).resolve()
    if not path.is_relative_to(Path(directory).resolve()):
        raise ValueError("evidence member escaped its bound directory")
    return path


def mapped_path(value, root):
    """Map only the exact original workspace prefix; never read a missing member elsewhere."""
    original = PureWindowsPath(str(value))
    if ".." in original.parts:
        raise ValueError("source binding contains parent traversal")
    if original.is_absolute():
        prefix = ORIGINAL_ROOT.parts
        if tuple(part.casefold() for part in original.parts[:len(prefix)]) != tuple(part.casefold() for part in prefix):
            raise ValueError("absolute source binding is outside the original workspace")
        relative = original.parts[len(prefix):]
    else:
        if original.drive:
            raise ValueError("drive-relative source binding is forbidden")
        relative = original.parts
    mapped = Path(root).resolve().joinpath(*relative).resolve()
    if not mapped.is_relative_to(Path(root).resolve()):
        raise ValueError("mapped source binding escaped --root")
    return mapped


def verify_files(directory, bindings):
    for name, expected in bindings.items():
        path = safe_child(directory, name)
        if not path.is_file() or sha(path) != expected:
            raise ValueError("missing or changed bound evidence: " + str(path))
    return len(bindings)


def sealed_candidate(directory):
    """The verifier must never recover missing files into an immutable evidence tree."""
    from ioabench.v5.ai_generation.direct_deepseek import candidate_result
    if not all((directory / name).is_file() for name in ("RESULT.json", "TERMINAL.json")):
        raise ValueError("candidate lacks a complete terminal seal; verifier will not reconstruct it")
    return candidate_result(directory)


def inventory(directory, *, except_names=()):
    return {path.relative_to(directory).as_posix(): sha(path) for path in Path(directory).rglob("*")
            if path.is_file() and path.name not in except_names and not path.name.endswith(".lock")
            and "__pycache__" not in path.parts}


def ledger_inventory(out):
    return {path.relative_to(out).as_posix(): sha(path) for path in out.rglob("*") if path.is_file()
            and (path.name.endswith("LEDGER.jsonl") or path.name.endswith("ATTEMPTS.jsonl"))}


@contextmanager
def no_network():
    """Windows asyncio's internal loopback socketpair is the sole connection exception."""
    import urllib.request
    from ioabench.models import aihubmix, deepseek
    counts = {"provider_http_or_external_network_attempts": 0, "windows_asyncio_loopback_connections": 0}
    saved = [(deepseek, "urlopen", deepseek.urlopen), (aihubmix, "urlopen", aihubmix.urlopen),
             (urllib.request, "urlopen", urllib.request.urlopen),
             (socket.socket, "connect", socket.socket.connect),
             (socket.socket, "connect_ex", socket.socket.connect_ex),
             (socket.socket, "sendto", socket.socket.sendto), (socket, "getaddrinfo", socket.getaddrinfo)]
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def forbidden(*args, **kwargs):
        counts["provider_http_or_external_network_attempts"] += 1
        raise AssertionError("provider HTTP and external network forbidden during verification")

    def allowed_connect(original):
        def guarded(sock, address):
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                counts["windows_asyncio_loopback_connections"] += 1
                return original(sock, address)
            return forbidden()
        return guarded

    def addresses(host, *args, **kwargs):
        if host in {"127.0.0.1", "::1", "localhost", None}:
            return getaddrinfo(host, *args, **kwargs)
        return forbidden()

    deepseek.urlopen = aihubmix.urlopen = urllib.request.urlopen = forbidden
    socket.socket.connect, socket.socket.connect_ex = allowed_connect(connect), allowed_connect(connect_ex)
    socket.socket.sendto, socket.getaddrinfo = forbidden, addresses
    try:
        yield counts
    finally:
        for owner, name, value in saved:
            setattr(owner, name, value)


def verify_audit(directory, root):
    from ioabench.hashing import canonical_sha256
    from ioabench.v5.ai_generation.development_audit import (
        CURRENT_PROTOCOL, ERROR_CODES, SYSTEM, SYSTEM_V11, VERSION, _history_facts, _observations, validate_review,
    )
    from ioabench.v5.ai_generation.direct_deepseek import parameters
    from ioabench.v5.ai_generation.factory import decode_json
    packet = read(directory / "AUDIT_PACKET.json")
    source = mapped_path(packet["source_binding"]["directory"], root)
    sealed_candidate(source)
    verify_files(source, packet["source_binding"]["files"])
    if not {"RESULT.json", "TERMINAL.json"} <= set(packet["source_binding"]["files"]):
        raise ValueError("audit source binding omitted its result or terminal")
    manifest = read(source / "MANIFEST.json")
    if manifest["source_sha256"] != packet["source_binding"]["runtime_sha256"]:
        raise ValueError("audit source runtime differs from the generator manifest")
    result, terminal = read(directory / "AUDIT_RESULT.json"), read(directory / "AUDIT_TERMINAL.json")
    if canonical_sha256(result) != terminal["result_sha256"] or result["packet_sha256"] != canonical_sha256(packet):
        raise ValueError("audit packet/result terminal seal changed")
    if packet["version"] not in {VERSION, CURRENT_PROTOCOL} or result["version"] != packet["version"]:
        raise ValueError("unknown or changed frozen audit protocol")
    actual = inventory(directory, except_names={"AUDIT_RESULT.json", "AUDIT_TERMINAL.json"})
    if terminal["evidence_sha256"] != actual:
        raise ValueError("audit terminal evidence inventory differs")
    bindings = read(directory / "DOCUMENT_BINDINGS.json")
    if set(packet["documents"]) != {"cases", "execution", "history", "replay", "schema"}:
        raise ValueError("audit packet omitted a required evidence dimension")
    expected_documents = {"inputs/" + name + ".json": value for name, value in packet["documents"].items()}
    if set(bindings) != set(expected_documents):
        raise ValueError("audit input document inventory is incomplete")
    verify_files(directory, bindings)
    for name, value in expected_documents.items():
        if read(safe_child(directory, name)) != value:
            raise ValueError("audit input differs from the sealed packet")
    if result["status"] == "DEV_AUTO_AUDITED":
        pair = read(source / "PAIR.json")
        expected_cases = [{"metadata": {key: value for key, value in case.items()
                                       if key not in {"world", "oracle", "provenance"}},
                           "scenario_world": case["world"], "oracle_hidden": case["oracle"]} for case in pair]
        rows = read(source / "STRICT_REFERENCE_RESULTS.json")
        expected_runs = [{"arm": row["arm"], "case_id": row["case_id"], "run_ordinal": ordinal,
                          "actions": row.get("trace", {}).get("actions", []),
                          "events": row.get("trace", {}).get("events", []),
                          "final_state": row.get("trace", {}).get("final_state", {}), "error": row.get("error")}
                         for ordinal, row in enumerate(rows)]
        documents = packet["documents"]
        if (documents["cases"] != expected_cases or documents["execution"]["runs"] != expected_runs
                or documents["execution"]["sut_visible"] != _observations(rows, provenance=packet["version"] == CURRENT_PROTOCOL)
                or documents["history"] != [_history_facts(item) for item in read(source / "HISTORY_DEDUP.json")]
                or documents["replay"] != [{key: value for key, value in row.items() if key != "passed"}
                                          for row in read(source / "REPLAY.json")]):
            raise ValueError("accepted audit documents differ from their sealed source facts")
        if "tool_observation_consistency" in documents["execution"]:
            from ioabench.v5.core.trace_integrity import inspect_tool_observations
            expected_consistency = [inspect_tool_observations(row["trace"]) for row in rows]
            if (documents["execution"]["tool_observation_consistency"] != expected_consistency
                    or any(row["mismatches"] or row["alignment_errors"] for row in expected_consistency)):
                raise ValueError("accepted audit ignores contradictory actual SUT tool observations")
    settings_path = directory / "AUDIT_SETTINGS.json"
    max_tokens = read(settings_path)["max_tokens"] if settings_path.exists() else 16384
    if max_tokens not in {16384, 32768, 65536}:
        raise ValueError("audit has an undocumented frozen output budget")
    if len({row["effort"] for row in result["reviews"]}) != len(result["reviews"]):
        raise ValueError("audit repeated a review condition")
    for row in result["reviews"]:
        if row["effort"] not in {"high", "max"}:
            raise ValueError("audit uses an undocumented review condition")
        if read(directory / ("AUDIT_" + row["effort"] + ".json")) != row:
            raise ValueError("audit review row differs from the terminal result")
        if "review" in row:
            errors = validate_review(row["review"], directory, bindings)
            if not set(errors) <= set(row["validation_errors"]):
                raise ValueError("audit omitted invalid evidence references or review-contract failures")
            response = read(directory / ("AUDIT_" + row["effort"] + "_RESPONSE.json"))
            if decode_json(response["text"]) != row["review"] or response["usage"] != row["usage"]:
                raise ValueError("audit review or usage differs from the actual response")
            if result["status"] == "DEV_AUTO_AUDITED" and (response["finish_reason"] != "stop" or response["tool_calls"]
                    or response["model_id"] != "deepseek-flash" or row.get("served_model_id") != "deepseek-flash"
                    or response["provider_metadata"].get("model") != "deepseek-flash"
                    or response["provider_metadata"].get("_transport", {}).get("http_status") != 200
                    or response["provider_metadata"].get("_transport", {}).get("endpoint") != "https://api.deepseek.com/chat/completions"):
                raise ValueError("accepted audit lacks a complete official DeepSeek response")
        if row["request_id"] != "audit-" + row["effort"] + "-" + canonical_sha256(packet)[:16]:
            raise ValueError("audit request identity is not bound to its packet and effort")
        request_binding = read(directory / "model_io" / row["request_id"] / "REQUEST_BINDING.json")
        request = request_binding["binding"]["request"]
        if request_binding["sha256"] != canonical_sha256(request_binding["binding"]):
            raise ValueError("audit request binding hash differs")
        if (request_binding["binding"]["role"] != "DEV_AUDITOR" or request.get("tools")
                or [message["role"] for message in request["messages"]] != ["system", "user"]):
            raise ValueError("audit context is not an isolated auditor exchange")
        contracts = request_binding["binding"]["contracts"]
        if len(contracts) != 1:
            raise ValueError("official audit silently changed model or fallback")
        contract = contracts[0]
        if (contract["profile"]["provider"] != "deepseek" or contract["profile"]["model_id"] != "deepseek-flash"
                or contract["profile"]["role"] != "DEV_AUDITOR" or request["role_metadata"].get("role") != "DEV_AUDITOR"
                or contract["parameters"] != parameters(row["effort"], max_tokens=max_tokens)
                or request.get("parameters") != {}):
            raise ValueError("audit request model, role or documented effort differs")
        system = SYSTEM_V11 if packet["version"] == CURRENT_PROTOCOL else SYSTEM
        if request["messages"][0]["content"] != system + "Allowed error_codes: " + ", ".join(sorted(ERROR_CODES)):
            raise ValueError("audit request changed the frozen review instructions")
        response_path = directory / "model_io" / row["request_id"] / "RESPONSE.json"
        if "review" in row:
            receipt = read(response_path)
            if (receipt["binding_sha256"] != request_binding["sha256"] or receipt["response"] != response
                    or receipt["response_sha256"] != canonical_sha256(response)):
                raise ValueError("audit response differs from the durable router receipt")
        expected_user = {"documents": {name: {"file": "inputs/" + name + ".json", "sha256": bindings["inputs/" + name + ".json"],
                                              "value": value} for name, value in packet["documents"].items()}}
        if json.loads(request["messages"][1]["content"]) != expected_user:
            raise ValueError("audit request differs from the frozen evidence documents")
    if result["status"] == "DEV_AUTO_AUDITED" and (packet["hard_gate_errors"] or len(result["reviews"]) != 2 or any(
            row["validation_errors"] or row.get("review", {}).get("verdict") != "ACCEPT" for row in result["reviews"])):
        raise ValueError("auto-audit passed without two valid evidence-bound accepts")
    if any(result.get(key) is not False for key in ("formal_accepted", "machine_qualified", "same_model_audit_independent_science")):
        raise ValueError("audit makes unsupported scientific claims")
    return {"directory": directory.relative_to(root).as_posix(), "source_directory": source.relative_to(root).as_posix(),
        "status": "PASS", "audit_status": result["status"], "mapped_source_hashes_verified": True,
        "tool_observation_gate_present": "tool_observation_consistency" in packet["documents"]["execution"],
        "packet_bytes_sha256": sha(directory / "AUDIT_PACKET.json"), "result": result}


def verify_admission(path, root, audits):
    from ioabench.hashing import canonical_sha256
    value = read(path)
    source = mapped_path(value["source_directory"], root)
    sealed_candidate(source)
    audit = audits[(path.parent / "audit").resolve()]
    if audit["source_directory"] != source.relative_to(root).as_posix():
        raise ValueError("admission and audit refer to different sources")
    if value["audit_status"] != audit["result"]["status"]:
        raise ValueError("admission changed its actual audit outcome")
    if (sha(source / "RESULT.json") != value["source_result_sha256"] or sha(source / "PAIR.json") != value["pair_sha256"]
            or canonical_sha256(audit["result"]) != value["audit_result_sha256"]):
        raise ValueError("admission source/audit hash binding differs")
    replays = read(source / "REPLAY.json")
    supplemental = path.parent / "supplemental"
    if (supplemental / "SUPPLEMENTAL_BINDING.json").is_file():
        binding = read(supplemental / "SUPPLEMENTAL_BINDING.json")
        if binding["source_pair_sha256"] != sha(source / "PAIR.json"):
            raise ValueError("supplemental batch belongs to a different pair")
        if binding["evidence_sha256"] != inventory(supplemental, except_names={"SUPPLEMENTAL_BINDING.json"}):
            raise ValueError("supplemental evidence binding differs")
        if [json.loads(line) for line in (supplemental / "CASES.jsonl").read_text(encoding="utf-8").splitlines()] != read(source / "PAIR.json"):
            raise ValueError("supplemental cases differ from the retained pair")
        replays += read(supplemental / "REPLAY.json")
    if value["recorded_strict_replays"] != len(replays):
        raise ValueError("admission invented a strict Replay count")
    if value["suite"] == "T322" and value["status"] == "DEV_ACCEPTED":
        raise ValueError("T322 historical uncertainty cannot become DEV_ACCEPTED")
    if value["status"] == "DEV_ACCEPTED" and (value["hard_gate_errors"] or value["history_scope"] != "FULL_HISTORY"
            or audit["result"]["status"] != "DEV_AUTO_AUDITED" or len(replays) < 6
            or not all(row.get("passed") is True for row in replays)):
        raise ValueError("development admission bypassed a hard, audit, history or strict Replay gate")
    vector = value["structural_vector"]
    if (vector["suite"] != value["suite"] or vector["structural_cell_sha256"] != canonical_sha256(vector["runtime_consumed"])
            or vector["difficulty"]["calibrated"] is not False
            or vector["simulation_only"] != (value["suite"] in {"T361", "T362", "T363"})):
        raise ValueError("admission structural vector makes inconsistent novelty or simulation claims")
    if any(value.get(key) is not False for key in ("formal_accepted", "machine_qualified", "same_model_audit_independent_science")) or value.get("new_scientific_families") != 0:
        raise ValueError("development admission makes unsupported scientific claims")
    return {"id": value["id"], "status": "PASS", "admission_status": value["status"], "strict_replays": len(replays)}


def verify_forensic(out, root, baseline):
    """Recompute only historical observation comparisons; reanalysis remains labelled."""
    from ioabench.v5.core.trace_integrity import inspect_tool_observations
    path = out / "FORENSIC_TRACE_ALIASING.json"
    if not path.exists():
        return {"status": "NOT_RUN", "reason": "no frozen forensic report"}
    value = read(path)
    baseline_path = mapped_path(value["baseline_file"], root)
    if baseline_path != out / "BASELINE_CENSUS.json" or sha(baseline_path) != value["baseline_sha256"]:
        raise ValueError("forensic report is not bound to this retained baseline census")
    sources = {row["id"]: mapped_path(row["source_directory"], root) for row in baseline["pairs"]}
    source_rows, compared, mismatches, alignment_errors, affected = {}, 0, 0, 0, set()
    observed_pairs, observed_rows, reanalysis_pass = set(), set(), 0
    for row in value["rows"]:
        source = mapped_path(row["source_file"], root)
        if source != sources[row["pair_id"]] / "STRICT_REFERENCE_RESULTS.json" or sha(source) != row["source_sha256"]:
            raise ValueError("forensic trace input path or source hash changed")
        if source not in source_rows:
            source_rows[source] = read(source)
        original = source_rows[source][row["row_ordinal"]]
        identity = row["pair_id"], row["row_ordinal"]
        if identity in observed_rows or original["case_id"] != row["case_id"] or original["run_id"] != row["run_id"]:
            raise ValueError("forensic report omitted or repeated a trace identity")
        observed_rows.add(identity)
        observed_pairs.add(row["pair_id"])
        observations = inspect_tool_observations(original["trace"])
        if observations != row["historical_observations"]:
            raise ValueError("forensic observation conclusions differ from original retained trace bytes")
        compared += observations["compared"]
        mismatches += len(observations["mismatches"])
        alignment_errors += len(observations["alignment_errors"])
        if observations["mismatches"] or observations["alignment_errors"]:
            affected.add(row["pair_id"])
        reanalysis = row["current_engine_reanalysis"]
        if reanalysis.get("provider_calls") != 0 or not reanalysis.get("checks"):
            raise ValueError("forensic reanalysis lacks recorded checks or zero-call provenance")
        reanalysis_pass += all(item is True for item in reanalysis["checks"].values())
    if (observed_pairs != set(sources) or len(observed_rows) != sum(len(rows) for rows in source_rows.values())
            or value["pair_count"] != len(sources) or value["reference_rows"] != len(observed_rows)
            or value["historical_mismatch_count"] != mismatches or value["historical_alignment_error_count"] != alignment_errors
            or sorted(value["affected_pair_ids"]) != sorted(affected)
            or value["current_reanalysis_pass"] != reanalysis_pass
            or value["current_reanalysis_fail"] != len(observed_rows) - reanalysis_pass
            or value["provider_calls"] != 0 or value["new_generation_requests"] != 0
            or value["original_evidence_modified"] is not False or value["strict_historical_replay_claim"] is not False):
        raise ValueError("forensic report aggregates or scientific scope differ from bound evidence")
    return {"status": "PASS", "file_sha256": sha(path), "baseline_sha256": value["baseline_sha256"],
        "bound_source_files": len(source_rows), "historical_rows_rechecked": len(observed_rows),
        "actual_tool_observations_compared": compared, "historical_mismatch_count": mismatches,
        "historical_alignment_error_count": alignment_errors, "affected_pair_ids": sorted(affected),
        "recorded_current_reanalysis_pass": reanalysis_pass, "current_reanalysis_rerun": "NOT_RUN_BOUND_REPORT_ONLY",
        "strict_historical_replay_claim": False, "provider_calls": 0}


def verify_protected(out, root, scope):
    protected = read(out / "PROTECTED_BASELINE.json")["files"]
    members = None
    if scope == "included":
        inventory_path = root / "_snapshot/FILES.json"
        members = {row["path"] for row in read(inventory_path)}
    elif scope != "full":
        raise ValueError("unknown protection verification scope")
    verified, omitted = 0, 0
    for name, digest in protected.items():
        normalized = PureWindowsPath(name).as_posix()
        if members is not None and normalized not in members:
            omitted += 1
            continue
        path = mapped_path(name, root)
        if not path.is_file() or sha(path) != digest:
            raise ValueError("protected historical evidence missing or changed: " + str(path))
        verified += 1
        if verified % 10000 == 0:
            print(json.dumps({"phase": "protected-history", "scope": scope, "verified": verified}), flush=True)
    value = {"status": "PASS" if scope == "full" else "PASS_INCLUDED_SUBSET", "scope": scope,
        "protected_inventory_sha256": sha(out / "PROTECTED_BASELINE.json"), "protected_total": len(protected),
        "actual_files_verified": verified, "not_included": omitted,
        "not_included_status": "NOT_INCLUDED" if omitted else "NONE", "provider_calls": 0}
    if scope == "included":
        live = out / "PROTECTED_VERIFICATION.json"
        if not live.is_file():
            raise ValueError("extracted package omitted its live full-history protection receipt")
        receipt = read(live)
        if (receipt.get("status") != "PASS" or receipt.get("changes") != []
                or receipt.get("file_count") != len(protected) or receipt.get("provider_calls") != 0):
            raise ValueError("packaged live full-history protection receipt is invalid")
        value.update(package_inventory_sha256=sha(root / "_snapshot/FILES.json"),
            live_full_history_receipt={"sha256": sha(live), **receipt},
            full_history_reverified_here="NOT_RUN_NOT_INCLUDED")
    return value


def baseline_replay_jobs(baseline, root, *, quarantined_pair_ids=()):
    """Resolve retained pairs and their original runtimes only inside the supplied root."""
    jobs, identities, directories = [], set(), set()
    quarantined = set(quarantined_pair_ids)
    for row in baseline["pairs"]:
        directory = mapped_path(row["source_directory"], root)
        if row["id"] in identities or directory in directories:
            raise ValueError("baseline census repeats a pair identity or source directory")
        identities.add(row["id"])
        directories.add(directory)
        runtime = row["source_runtime_sha256"]
        revision = safe_child(directory.parent.parent / "source_revisions", runtime)
        if not revision.is_relative_to(Path(root).resolve()) or not revision.is_dir():
            raise ValueError("baseline source snapshot missing from this package")
        if read(directory / "MANIFEST.json")["source_sha256"] != runtime:
            raise ValueError("baseline generator manifest differs from its bound source runtime")
        count = row["reference_replay_rows"]
        if (not isinstance(count, int) or isinstance(count, bool) or count <= 0
                or len(read(directory / "REPLAY.json")) != count):
            raise ValueError("baseline census invented a strict Replay count")
        if not (directory / "strict/artifacts/v5/evaluations").is_dir():
            raise ValueError("baseline pair is missing its strict evidence")
        jobs.append({"directory": str(directory), "runtime_sha256": runtime,
                     "source_revision_directory": str(revision), "required_positive": True,
                     "cohort": "baseline", "baseline_id": row["id"], "expected_replay_count": count,
                     "historical_observation_quarantined": row["id"] in quarantined})
    if baseline.get("baseline_replay_rows", sum(job["expected_replay_count"] for job in jobs)) != sum(
            job["expected_replay_count"] for job in jobs):
        raise ValueError("baseline aggregate strict Replay count differs from its pairs")
    return jobs


def verify_revision(jobs, source, root):
    """This function runs only in a fresh process importing the exact retained source."""
    source, root = Path(source).resolve(), Path(root).resolve()
    if not source.is_relative_to(root):
        raise ValueError("source snapshot is outside --root")
    sys.path.insert(0, str(source / "src"))
    from ioabench.hashing import canonical_sha256
    from ioabench.models import ModelProfile
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5 import evaluation
    from ioabench.v5.replay import replay_case
    runtime = source_tree_hash(source)
    if runtime != source.name:
        raise ValueError("retained source snapshot hash differs")
    reports = []
    with no_network() as guard:
        for job in jobs:
            directory = Path(job["directory"]).resolve()
            if not directory.is_relative_to(root) or job["runtime_sha256"] != runtime:
                raise ValueError("strict job is outside --root or bound to a different source revision")
            before = inventory(directory)
            checks, actual_replays, resumes = [], [], 0
            manifests = sorted((directory / "strict/artifacts/v5/evaluations").glob("*/manifest.json"))
            if not manifests:
                raise ValueError("strict evidence directory has no pinned run manifest")
            for path in manifests:
                manifest = read(path)
                if manifest["source_sha256"] != runtime:
                    raise ValueError("strict run is bound to a different source revision")
                rows = evaluation.read_results(path.parent)
                complete = len(rows) == len(manifest["cases"]) and all(row["status"] == "COMPLETED" for row in rows)
                if job.get("required_positive", True) and not complete:
                    raise ValueError("positive engineering sample has an incomplete strict matrix")
                for row in rows:
                    if row["status"] != "COMPLETED":
                        checks.append({"case_id": row["case_id"], "status": "NOT_RUN", "reason": "recorded episode is not complete"})
                        continue
                    result = replay_case(directory / "strict", manifest["run_id"], row["case_id"])
                    if result.get("passed") is not True or result.get("provider_calls") != 0:
                        raise ValueError("exact-source strict Replay failed")
                    actual_replays.append(result)
                    checks.append({"case_id": row["case_id"], "run_id": manifest["run_id"], "status": "PASS", "checks": result.get("checks", {})})
                if not complete:
                    # Resuming an incomplete batch would execute new episodes, not verify retained ones.
                    continue
                with tempfile.TemporaryDirectory(prefix="ioa-dev-reference-resume-") as temporary:
                    copied = Path(temporary) / "strict"
                    shutil.copytree(directory / "strict", copied)
                    copied_run = copied / "artifacts/v5/evaluations" / manifest["run_id"]
                    original_rows = evaluation.read_results(copied_run)
                    evaluation.run_batch(copied, directory / "CASES.jsonl", run_id=manifest["run_id"],
                        profile=ModelProfile(**manifest["profile"]), parameters=manifest["parameters"],
                        reference_policy=manifest["reference_policy"], expected_identity=manifest["expected_identity"],
                        max_attempts=manifest["max_attempts"], resume=True)
                    if evaluation.read_results(copied_run) != original_rows:
                        raise ValueError("reference resume appended or changed terminal results")
                    resumes += 1
            if (directory / "REPLAY.json").is_file() and sorted(map(canonical_sha256, read(directory / "REPLAY.json"))) != sorted(map(canonical_sha256, actual_replays)):
                raise ValueError("actual exact-source Replay differs from the recorded Replay matrix")
            if "expected_replay_count" in job and len(actual_replays) != job["expected_replay_count"]:
                raise ValueError("actual baseline strict Replay count differs from its census")
            if inventory(directory) != before:
                raise ValueError("strict verification changed sealed evidence")
            reports.append({"directory": str(directory), "status": "PASS" if checks and all(row["status"] == "PASS" for row in checks) else "NOT_RUN_INCOMPLETE_FAILED_CANDIDATE", "strict_replays": checks,
                            "required_positive": job.get("required_positive", True),
                            "cohort": job.get("cohort", "candidate"), "baseline_id": job.get("baseline_id"),
                            "historical_observation_quarantined": job.get("historical_observation_quarantined", False),
                            "reference_batch_resumes": resumes, "sealed_bytes_unchanged": True})
    if guard["provider_http_or_external_network_attempts"]:
        raise ValueError("strict verification attempted network access")
    return {"status": "PASS", "runtime_sha256": runtime, "jobs": reports, "network_guard": guard, "provider_calls": 0}


CLI_GUARD = """
import json,runpy,sys
from pathlib import Path
root,verifier,script,receipt,out=sys.argv[1:]
sys.path[:0]=[str(Path(root)/'src'),str(Path(verifier).parent)]
from verify_development_factory import no_network
try:
    with no_network() as guard:
        sys.argv=[script,'--out',out,'--phase','resume','--original-root','D:/Project/ioa_codex_spec']
        runpy.run_path(script,run_name='__main__')
finally:
    Path(receipt).write_text(json.dumps(guard),encoding='utf-8')
"""


def verify_cli(out, root):
    script = root / "scripts/v5/run_development_factory.py"
    if not script.is_file():
        raise ValueError("packaged development CLI is missing from --root")
    before = ledger_inventory(out)
    with tempfile.TemporaryDirectory(prefix="ioa-dev-cli-resume-") as temporary:
        receipt = Path(temporary) / "network-guard.json"
        process = subprocess.run([sys.executable, "-B", "-c", CLI_GUARD, str(root), str(Path(__file__).resolve()),
            str(script), str(receipt), str(out)], cwd=root, capture_output=True, text=True, timeout=900)
        guard = read(receipt) if receipt.exists() else {"provider_http_or_external_network_attempts": None}
    if ledger_inventory(out) != before or guard["provider_http_or_external_network_attempts"] != 0:
        raise ValueError("CLI resume changed the request ledger or attempted network access")
    if process.returncode:
        return {"status": "FAIL", "returncode": process.returncode,
                "ledger_unchanged": True, "network_guard": guard, "stderr": process.stderr[-8000:],
                "limitation": "Extracted CLI resume must actually succeed using only --root evidence."}
    cli = read(out / "CLI_NO_RESEND.json")
    if cli.get("status") != "PASS" or cli.get("provider_calls") != 0 or cli.get("ledger_unchanged") is not True:
        raise ValueError("CLI no-resend receipt is invalid")
    return {"status": "PASS", "returncode": 0, "cli_receipt": cli, "ledger_unchanged": True, "network_guard": guard}


def verify(out, root, protection_scope="full"):
    sys.path.insert(0, str(root / "src"))
    from ioabench.runtime.full_manifest import source_tree_hash
    if not out.is_relative_to(root):
        raise ValueError("--out must be inside --root")
    ledgers = ledger_inventory(out)
    protected = verify_protected(out, root, protection_scope)
    baseline = read(out / "BASELINE_CENSUS.json")
    baseline_files = 0
    for row in baseline["pairs"]:
        source = mapped_path(row["source_directory"], root)
        sealed_candidate(source)
        if sha(source / "PAIR.json") != row["pair_sha256"] or sha(source / "RESULT.json") != row["source_result_sha256"]:
            raise ValueError("retained baseline pair/result changed")
        baseline_files += verify_files(source, row["source_evidence_sha256"])
    forensic = verify_forensic(out, root, baseline)
    candidates, revisions = [], {}
    jobs = baseline_replay_jobs(baseline, root, quarantined_pair_ids=forensic.get("affected_pair_ids", []))
    for path in sorted((out / "candidates").glob("*/MANIFEST.json")):
        if not (path.parent / "RESULT.json").is_file() or not (path.parent / "TERMINAL.json").is_file():
            raise ValueError("candidate lacks a complete terminal seal")
        value = sealed_candidate(path.parent)
        manifest = read(path)
        candidates.append({"id": path.parent.name, "status": "PASS", "candidate_status": value["status"]})
        if (path.parent / "strict/artifacts/v5/evaluations").is_dir():
            jobs.append({"directory": str(path.parent), "runtime_sha256": manifest["source_sha256"],
                         "required_positive": value["status"] == "PASS"})
        elif value["status"] == "PASS":
            raise ValueError("positive candidate is missing its strict evidence")
        else:
            candidates[-1]["strict_replay"] = "NOT_RUN_CANDIDATE_FAILED_BEFORE_STRICT_MATRIX"
    audits = {path.parent.resolve(): verify_audit(path.parent, root) for path in sorted(out.rglob("AUDIT_PACKET.json"))
              if "source_revisions" not in path.parts}
    admissions = [verify_admission(path, root, audits) for path in sorted((out / "reviews").glob("*/ADMISSION.json"))]
    for path in sorted((out / "reviews").glob("*/supplemental/SUPPLEMENTAL_BINDING.json")):
        binding = read(path)
        jobs.append({"directory": str(path.parent), "runtime_sha256": binding["source_runtime_sha256"]})
    revision_paths = {Path(job["source_revision_directory"]) for job in jobs
                      if "source_revision_directory" in job}
    revision_paths.update(path for path in (out / "source_revisions").iterdir() if path.is_dir())
    for path in sorted(revision_paths):
        if path.is_dir():
            if not path.resolve().is_relative_to(root):
                raise ValueError("source snapshot is outside --root")
            if source_tree_hash(path) != path.name:
                raise ValueError("source snapshot hash differs: " + str(path))
            revisions.setdefault(path.name, path)
    grouped = {}
    for job in jobs:
        if job["runtime_sha256"] not in revisions:
            raise ValueError("strict run source snapshot missing from this package")
        grouped.setdefault(job["runtime_sha256"], []).append(job)
    reports = []
    with tempfile.TemporaryDirectory(prefix="ioa-dev-exact-source-") as temporary:
        for revision, group in grouped.items():
            job_path, result_path = Path(temporary) / (revision + "-jobs.json"), Path(temporary) / (revision + "-result.json")
            job_path.write_text(json.dumps(group), encoding="utf-8")
            subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--out", str(out), "--root", str(root),
                "--source", str(revisions[revision]), "--jobs", str(job_path), "--result", str(result_path)], check=True, cwd=root)
            reports.append(read(result_path))
    cli = verify_cli(out, root)
    if ledger_inventory(out) != ledgers:
        raise ValueError("verification changed a request ledger")
    return {"status": "PASS" if cli["status"] == "PASS" else "FAIL",
        "provider_calls": 0, "ledger_unchanged": True, "baseline_pairs": len(baseline["pairs"]),
        "protected_history": protected,
        "baseline_bound_files_verified": baseline_files, "baseline_generation_evidence_unchanged": True,
        "baseline_exact_source_replay": {
            "status": "PASS", "pairs": len(baseline["pairs"]),
            "strict_replays": sum(len(job["strict_replays"]) for report in reports for job in report["jobs"]
                                  if job["cohort"] == "baseline"),
            "reference_batch_resumes": sum(job["reference_batch_resumes"] for report in reports for job in report["jobs"]
                                            if job["cohort"] == "baseline"),
            "historical_observation_quarantined_pairs": sorted(forensic.get("affected_pair_ids", [])),
            "historical_acceptance_changed": False},
        "historical_tool_observation_forensic": forensic,
        "candidate_seals": candidates, "audits": [{key: value for key, value in row.items() if key != "result"} for row in audits.values()],
        "admissions": admissions, "source_snapshots_verified": sorted(revisions), "exact_source_revisions": reports,
        "audit_tool_observation_gate_present": sum(row["tool_observation_gate_present"] for row in audits.values()),
        "audit_tool_observation_gate_absent_frozen_legacy": sum(not row["tool_observation_gate_present"] for row in audits.values()),
        "required_positive_replays": "PASS",
        "strict_replay_count": sum(check["status"] == "PASS" for report in reports for job in report["jobs"] for check in job["strict_replays"]),
        "actual_cli_resume": cli, "relocated_source_mapping": "STRICT_ORIGINAL_PREFIX_TO_ROOT_NO_FALLBACK"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--protection-scope", choices=("full", "included"), default="full")
    parser.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--jobs", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    out, root = args.out.resolve(), args.root.resolve()
    result = verify_revision(read(args.jobs), args.source.resolve(), root) if args.source else verify(out, root, args.protection_scope)
    destination = args.result or out / "DEVELOPMENT_VERIFICATION.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "provider_calls")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
