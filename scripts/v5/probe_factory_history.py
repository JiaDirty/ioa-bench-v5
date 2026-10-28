"""Execute fixed witness/naive policies on every indexed historical case; no provider."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.models import ModelProfile
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.history import attach_probe, verify_sources, POLICY_CONTRACT, PROBE_VERSION
from ioabench.v5.ai_generation.quality import QUALITY_VERSION
from ioabench.v5.core.case import case_from_dict, resolve_pointer, SUITES
from ioabench.v5.core.monitor import ledger_integrity
from ioabench.v5.dynamic.registry import get_adapter
from ioabench.v5.dynamic.runner import run_dynamic_case
from ioabench.v5.evaluation import atomic_json
from ioabench.v5.runner import run_case
from ioabench.v5.suites import load

PROFILE = ModelProfile("scripted", "reference-policy", {}, {}, role="REFERENCE_POLICY")
PROBE_RUN_VERSION = "ioabench.v5.history-probe-run/1.1.0"
EVIDENCE_VERSION = "ioabench.v5.history-probe-evidence/1.1.0"


def _source_case(root, index, record, documents):
    occurrence = record["occurrences"][0]
    name = occurrence["source"]
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or name not in index["source_sha256"]:
        raise ValueError("historical occurrence refers to an unbound source")
    if name not in documents:
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != index["source_sha256"][name]:
            raise ValueError("historical source changed while loading its case")
        text = content.decode("utf-8-sig")
        documents[name] = ([json.loads(line) if line.strip() else None for line in text.splitlines()]
                           if path.suffix.lower() == ".jsonl" else json.loads(text))
    line = occurrence["line"]
    if line is not None and (type(line) is not int or line < 1):
        raise ValueError("historical source line must be a positive integer or null")
    document = documents[name][line - 1] if line is not None else documents[name]
    case = case_from_dict(resolve_pointer(document, occurrence["pointer"]), allow_dynamic=True)
    if case.content_sha256() != record["case_sha256"] or case.suite_id != record["features"]["suite_id"]:
        raise ValueError("historical source case identity differs from index")
    return case


def _saved_probe(path, binding, index, record, contract_sha256, root, documents):
    if not binding.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != binding.read_text(encoding="ascii"):
        raise ValueError("historical probe evidence digest changed or is incomplete")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        saved = json.load(stream)
    if (saved.get("schema_version") != EVIDENCE_VERSION
            or saved.get("run_contract_sha256") != contract_sha256
            or saved.get("case_sha256") != record["case_sha256"]
            or saved.get("suite_id") != record["features"]["suite_id"]
            or saved.get("source_occurrence") != record["occurrences"][0]
            or not isinstance(saved.get("policy_execution"), dict)
            or set(saved["policy_execution"]) != {"witness", "naive"}
            or saved.get("status") not in {"PROBED", "INDETERMINATE"}):
        raise ValueError("historical probe evidence binding or schema changed")
    if saved["status"] == "PROBED":
        case = _source_case(root, index, record, documents)
        signature = attach_probe(index, case, saved["results"], policy_contract=POLICY_CONTRACT)
        if (saved.get("probe") != signature or saved.get("probe_status") != "PROBED"
                or saved["policy_execution"] != {"witness": "COMPLETED", "naive": "COMPLETED"}):
            raise ValueError("historical probe policy or behavioral evidence changed")
    else:
        if saved.get("probe") is not None or saved.get("probe_status") not in {"NOT_RUN", "FAILED"}:
            raise ValueError("indeterminate historical case cannot carry a behavioral signature")
        record["behavioral_probe_signature"] = None
    return saved


def probe(root, index_path, output, suites):
    index = json.loads(index_path.read_text(encoding="utf-8-sig"))
    verify_sources(root, index)
    contract = {"schema_version": PROBE_RUN_VERSION, "runtime_source_sha256": source_tree_hash(ROOT),
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(), "policy_contract": POLICY_CONTRACT,
        "quality_version": QUALITY_VERSION, "behavioral_probe_version": PROBE_VERSION,
        "projection_source_sha256": index["projection_source_sha256"],
        "suites": list(suites), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    contract_sha256 = canonical_sha256(contract)
    target = output / "RUN_CONTRACT.json"
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != contract:
        raise ValueError("history probe contract changed; use a new output directory")
    atomic_json(target, contract)
    documents, outcomes = {}, []
    selected = [row for row in index["records"] if row["features"]["suite_id"].split("-")[0] in suites]
    for record in selected:
        digest = record["case_sha256"]
        path = output / "cases" / (digest + ".json.gz")
        if path.exists():
            saved = _saved_probe(path, path.with_suffix(".sha256"), index, record,
                                 contract_sha256, root, documents)
        else:
            results = {}
            execution = {policy: "NOT_RUN" for policy in ("witness", "naive")}
            probe_status = "NOT_RUN"
            saved = {"schema_version": EVIDENCE_VERSION, "run_contract_sha256": contract_sha256,
                     "case_sha256": digest, "suite_id": record["features"]["suite_id"],
                     "source_occurrence": record["occurrences"][0], "policy_execution": execution}
            try:
                case = _source_case(root, index, record, documents)
                module = load(case.suite_id) if case.suite_id in SUITES else get_adapter(case.suite_id)
                for policy in ("witness", "naive"):
                    model = module.policies()[policy]
                    ident = "history-" + digest[:16] + "-" + policy
                    execution[policy] = "STARTED"
                    if case.suite_id in SUITES:
                        auxiliary = module.reference_auxiliary() if hasattr(module, "reference_auxiliary") else None
                        result = asyncio.run(run_case(output / "runner", case, model, PROFILE, run_id=ident,
                            parameters={"temperature": 0.0}, auxiliary=auxiliary))
                        if "trace" in result:
                            trace = SimpleNamespace(events=result["trace"]["events"],
                                actions=[SimpleNamespace(**action) for action in result["trace"]["actions"]])
                            result["monitor_report"] = {"ledger_integrity": ledger_integrity(trace)}
                    else:
                        result = run_dynamic_case(output / "runner", case, module, model, PROFILE,
                            run_id=ident, parameters={"temperature": 0.0})
                    results[policy] = result
                    execution[policy] = result["status"]
                probe_status = "FAILED"
                signature = attach_probe(index, case, results, policy_contract=POLICY_CONTRACT)
                saved.update(status="PROBED", probe_status="PROBED", probe=signature, results=results)
            except Exception as exc:
                execution.update({policy: "FAILED" for policy, status in execution.items() if status == "STARTED"})
                record["behavioral_probe_signature"] = None
                saved.update(status="INDETERMINATE", probe_status=probe_status, probe=None,
                             error_type=type(exc).__name__, error=str(exc), results=results)
            path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                json.dump(saved, stream, ensure_ascii=False, sort_keys=True)
            path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest(), encoding="ascii")
        outcomes.append({key: saved[key] for key in ("case_sha256", "suite_id", "status")})
        if len(outcomes) % 100 == 0:
            atomic_json(output / "PROGRESS.json", {"schema_version": PROBE_RUN_VERSION,
                "run_contract_sha256": contract_sha256, "finished": len(outcomes), "expected": len(selected),
                "statuses": dict(Counter(row["status"] for row in outcomes))})
    verify_sources(root, index)
    if source_tree_hash(ROOT) != contract["runtime_source_sha256"]:
        raise ValueError("runtime changed during historical probing")
    atomic_json(output / "INDEX_WITH_PROBES.json", index)
    report = {"schema_version": PROBE_RUN_VERSION, "run_contract_sha256": contract_sha256,
        "status": ("NOT_RUN" if not outcomes else "COMPLETED_WITH_EXPLICIT_GAPS"
                   if any(row["status"] != "PROBED" for row in outcomes) else "ALL_SELECTED_CASES_PROBED"),
        "policy_contract": POLICY_CONTRACT, "selected_cases": len(selected), "results": outcomes,
        "by_suite": {suite: dict(Counter(row["status"] for row in outcomes if row["suite_id"].split("-")[0] == suite)) for suite in suites},
        "provider_calls": 0, "verified_new_families": 0, "source_findings": index["findings"],
        "scope": "Current-runtime reference behavior on retained historical inputs; not historical-source replay or AI/human qualification."}
    atomic_json(output / "REPORT.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--suites", nargs="+", default=list(SUITES), choices=SUITES)
    args = parser.parse_args()
    from routed_t321_data_factory_s1 import _lock
    with _lock(ROOT / "artifacts/v5/overnight_runs/.writer.lock"):
        report = probe(ROOT, args.index, args.out, args.suites)
    print(json.dumps({key: value for key, value in report.items() if key not in {"results", "source_findings"}}, ensure_ascii=False))
