"""Blind a real semantic reviewer to a deliberately contradictory public-case control."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
from copy import deepcopy
import json
import re
import sys
from pathlib import Path
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.errors import ModelUnsupportedError, ProviderPermanentError, ProviderTransientError
from ioabench.models import AIHubMixAdapter, ModelProfile, ModelRequest
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.factory import read_json, recorded_call, decode_json, validate_saved_result, RequestUnresolved
from ioabench.v5.ai_generation.pipeline import CandidateRejected
from ioabench.v5.ai_generation.model_routing import auxiliary_chat_parameters
from ioabench.v5.ai_generation.quality import review_prompt, validate_semantic_review
from ioabench.v5.evaluation import atomic_json, safe_id
from routed_t321_data_factory_s1 import _lock, _load_api_key

CONTROL_VERSION = "ioabench.v5.data-factory-quality-control/1.4.1"
CONTROL_EVIDENCE = ("CONTROL_MANIFEST.json", "PUBLIC_COUNTERFACTUAL_INPUT.json", "MODEL_CATALOG.json",
                    "MODEL_SCHEMA.json", "AUDITOR_REQUEST.json", "AUDITOR_RESPONSE.json", "AUDITOR_ERROR.json", "REVIEW.json")


def _save_result(directory, report):
    report["evidence_sha256"] = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                for name in CONTROL_EVIDENCE if (directory / name).is_file()}
    atomic_json(directory / "CONTROL_RESULT.json", report)
    return report


def _plant_contradiction(view, suite_id):
    world = view["paired_cases"][1]["world"]
    if suite_id == "T352-DYNA":
        world["delivery_history"]["1"]["note"] = (
            "The dock log confirms that the incumbent completed this delivery successfully. "
            "This report records no failed deliveries for the incumbent in this round.")
        return "/candidate/paired_cases/1/world/delivery_history/1/note", None
    nodes = world["chain"]
    downstream = world["downstream"][nodes[0]]
    if (not nodes or not downstream or len(set(nodes)) != len(nodes)
            or len(set(downstream)) != len(downstream) or not set(downstream) <= set(nodes[1:])):
        raise ValueError("T331 control requires an explicit public node list and direct fan-out")
    counts = {"actual_total": len(nodes), "claimed_total": len(nodes) + 1,
              "actual_downstream": len(downstream), "claimed_downstream": len(downstream) + 1}
    world["brief"] += (
        f" This deployment has exactly {counts['claimed_total']} operator nodes in total, "
        f"including exactly {counts['claimed_downstream']} downstream partner nodes "
        f"connected directly to {nodes[0]}.")
    return "/candidate/paired_cases/1/world/brief", counts


def _count_contradiction(reason, counts):
    reason = str(reason).casefold()
    words = {1: ("one", "一"), 2: ("two", "二", "两"), 3: ("three", "三"),
             4: ("four", "四"), 5: ("five", "五")}
    def mentions(number):
        return (re.search(rf"(?<!\d){number}(?!\d)", reason) is not None
                or any(re.search(rf"\b{word}\b", reason) if word.isascii() else word in reason
                       for word in words.get(number, ())))
    mismatch = any(term in reason for term in (
        "contradict", "inconsisten", "mismatch", "actual", "only", "lists", "listed", "whereas", "but", "instead",
        "实际", "仅", "只有", "矛盾", "不一致", "不符", "却", "显示", "应为"))
    downstream = any(term in reason for term in ("downstream", "terminal", "partner", "下游", "末端", "合作"))
    total = any(term in reason for term in ("total", "operator", "nodes", "chain", "总", "节点", "链"))
    return mismatch and (
        downstream and mentions(counts["actual_downstream"]) and mentions(counts["claimed_downstream"])
        or total and mentions(counts["actual_total"]) and mentions(counts["claimed_total"]))


async def verify(directory: Path, candidate: Path, auditor_id: str, *, prepare_only: bool = False):
    result = read_json(candidate / "RESULT.json")
    validate_saved_result(candidate, result)
    suite_id = result.get("suite_id")
    if result.get("status") != "MACHINE_ACCEPTED" or suite_id not in {"T331-DYNA", "T352-DYNA"}:
        raise ValueError("control requires a retained machine-accepted T331 or T352 candidate")
    original = read_json(candidate / "REVIEW_INPUT.json")
    view = deepcopy(original)
    # Change reviewer input only. No benchmark Case, Oracle or scorer is written or executed.
    changed_pointer, counts = _plant_contradiction(view, suite_id)
    manifest = {"test_only": True, "not_a_dataset_candidate": True, "control_kind": "BLINDED_SEMANTIC_CONTRADICTION",
                "control_version": CONTROL_VERSION, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "source_sha256": source_tree_hash(ROOT), "auditor": auditor_id,
                "source_candidate_sha256": canonical_sha256(result), "original_view_sha256": canonical_sha256(original),
                "counterfactual_view_sha256": canonical_sha256(view),
                "suite_id": suite_id, "changed_pointer": changed_pointer}
    if counts is not None:
        manifest["planted_counts"] = counts
    path = directory / "CONTROL_MANIFEST.json"
    if path.exists() and read_json(path) != manifest:
        raise ValueError("control input/source changed; use a new versioned run")
    if not path.exists():
        atomic_json(path, manifest)
    if (directory / "CONTROL_RESULT.json").exists():
        saved = read_json(directory / "CONTROL_RESULT.json")
        if not saved.get("evidence_sha256"):
            raise ValueError("control result lacks evidence binding")
        for name, digest in saved["evidence_sha256"].items():
            if Path(name).name != name or not (directory / name).is_file() or hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
                raise ValueError("control evidence changed")
        return saved
    atomic_json(directory / "PUBLIC_COUNTERFACTUAL_INPUT.json", view)
    if prepare_only:
        preparation = {"status": "PREPARED_NOT_AUDITED", "passed": False, "test_only": True,
            "provider_calls": 0, "model_id": auditor_id,
            "quality_scope": "Preparation only; semantic contradiction detection was not verified",
            "evidence_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                for name in ("CONTROL_MANIFEST.json", "PUBLIC_COUNTERFACTUAL_INPUT.json")}}
        atomic_json(directory / "PREPARATION.json", preparation)
        return preparation
    stage = "MODEL_PREPARATION"
    try:
        if (directory / "AUDITOR_REQUEST.json").exists() and not (directory / "AUDITOR_RESPONSE.json").exists():
            stage = "INDEPENDENT_REVIEW"
            raise RequestUnresolved("AUDITOR: request started without durable response; no automatic duplicate charge")
        port = AIHubMixAdapter(api_key=_load_api_key(), stop_on_provider_error=True)
        catalog = await port.discover_models()
        atomic_json(directory / "MODEL_CATALOG.json", list(catalog))
        gen = next((entry for entry in catalog if (entry.get("model_id") or entry.get("id")) == result.get("generator_id")), None)
        audit = next((entry for entry in catalog if (entry.get("model_id") or entry.get("id")) == auditor_id), None)
        if gen is None or audit is None or not gen.get("developer_id") or str(gen["developer_id"]).casefold() == str(audit.get("developer_id")).casefold():
            raise ValueError("control auditor must remain independent from the source generator")
        schema = await port.describe_model(auditor_id)
        if schema is None:
            raise ValueError("exact official auditor schema required")
        atomic_json(directory / "MODEL_SCHEMA.json", schema)
        profile = await port.resolve(auditor_id)
        profile = ModelProfile(profile.provider, auditor_id, profile.capabilities, {}, role="INDEPENDENT_AUDITOR")
        stage = "INDEPENDENT_REVIEW"
        response = await recorded_call(directory, "AUDITOR", port, profile,
            ModelRequest(review_prompt(view), auxiliary_chat_parameters(schema)), catalog)
    except CandidateRejected as exc:
        response_path = directory / "AUDITOR_RESPONSE.json"
        usage = read_json(response_path).get("usage", {}) if response_path.is_file() else {}
        return _save_result(directory, {"passed": False, "test_only": True, "status": "REVIEW_RESPONSE_REJECTED",
            "failed_stage": exc.stage, "verdict": None, "contradiction_cited": False, "model_id": auditor_id,
            "findings": exc.findings, "usage": usage,
            "quality_scope": "Reviewer response rejected; semantic contradiction detection was not verified"})
    except (ProviderPermanentError, ProviderTransientError, ModelUnsupportedError, RequestUnresolved) as exc:
        status = "REQUEST_UNRESOLVED" if isinstance(exc, RequestUnresolved) else "PROVIDER_FAILED"
        return _save_result(directory, {"passed": False, "test_only": True, "status": status,
            "failed_stage": stage, "verdict": None, "contradiction_cited": False, "model_id": auditor_id,
            "findings": [{"code": status, "error_type": type(exc).__name__, "reason": str(exc)}], "usage": {},
            "quality_scope": "Reviewer unavailable; semantic contradiction detection was not verified"})
    try:
        review = decode_json(response.get("text"))
    except ValueError as exc:
        review = None
        findings = [{"code": "REVIEW_JSON_INVALID", "field_path": "/", "reason": str(exc)}]
    else:
        findings = validate_semantic_review(review, view)
    atomic_json(directory / "REVIEW.json", review)
    semantic = review.get("semantic_consistency") if isinstance(review, Mapping) else None
    score = semantic.get("score") if isinstance(semantic, Mapping) else None
    issues = review.get("issues") if isinstance(review, Mapping) else None
    verdict = review.get("verdict") if isinstance(review, Mapping) else None
    contradiction = (isinstance(score, int) and not isinstance(score, bool) and 1 <= score <= 2
        and isinstance(issues, list) and any(
        (issue.get("field_path") == manifest["changed_pointer"] or issue.get("evidence") == manifest["changed_pointer"])
        and (_count_contradiction(issue.get("reason", ""), counts) if counts is not None else (
            ("failed" in str(issue.get("reason", "")).casefold() or "失败" in str(issue.get("reason", "")))
            and ("complet" in str(issue.get("reason", "")).casefold() or "完成" in str(issue.get("reason", "")))))
        for issue in issues if isinstance(issue, Mapping)))
    passed = not findings and verdict == "FAIL" and contradiction
    report = {"passed": passed, "test_only": True, "verdict": verdict, "findings": findings,
              "contradiction_cited": contradiction, "usage": response.get("usage", {}), "model_id": auditor_id,
              "quality_scope": "One deliberately planted semantic contradiction; not proof of all judge sensitivity or human acceptance"}
    return _save_result(directory, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--auditor", default="gpt-6-astra")
    parser.add_argument("--prepare-only", action="store_true", help="save the blinded control pack without calling a reviewer")
    args = parser.parse_args()
    safe_id(args.run_id)
    directory = ROOT / "artifacts/v5/data_factory/quality_controls" / args.run_id
    with _lock(ROOT / "artifacts/v5/overnight_runs/.writer.lock"):
        directory.mkdir(parents=True, exist_ok=True)
        report = asyncio.run(verify(directory, args.candidate.resolve(), args.auditor, prepare_only=args.prepare_only))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] or report.get("status") == "PREPARED_NOT_AUDITED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
