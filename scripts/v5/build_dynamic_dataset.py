"""Build a CANDIDATE_EXPERIMENTAL dataset from a dynamic-slice family expansion (M8 first-priority fill).

For one slice module this runs the full offline production chain:
  slice.generate(families) -> check_pair_dynamic per pair -> structural signatures
  -> cross-batch dedup (within run + against the frozen 5.1.5 classic families of the same suite)
  -> append-only experimental dataset in a NEW namespace (data/v5/dynamic_experimental/).

Deterministic hard gates only; no provider calls; the frozen 5.1.5/5.1.6 datasets are read-only
reference for dedup, never modified. Accepted pairs carry their gate report digest and structural
signature; rejected pairs carry machine-readable reasons. Re-running with the same seed into an
existing run directory is refused (append-only evidence, no overwrites).

The output is CANDIDATE_EXPERIMENTAL: it never enters Gate C pools, the confirmation pilot or any
campaign denominator without Gate C/D and a PI decision (PI-V5-007).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.dynamic.gates import check_pair_dynamic  # noqa: E402
from ioabench.v5.dynamic.family_registry import classify, register
from ioabench.v5.dynamic.signature import (family_digest, signature,
                                           signature_digest, structural_delta)  # noqa: E402

BASELINE_DIR = ROOT / "data/v5/datasets"
FAMILY_REGISTRY = ROOT / "data/v5/dynamic_experimental/_family_registry.jsonl"
EXPERIMENTAL_DIR = ROOT / "data/v5/dynamic_experimental"
BASELINE = "5.1.5-candidate-20261006"
T332_LOCAL = "5.1.6-candidate-20261009"


def load_slice(name: str):
    return importlib.import_module(f"ioabench.v5.dynamic.{name}")


def slice_scenario(module, slice_name: str):
    """The slice's scenario class name is not uniform (T321 has structure A/B variants); resolve
    via an explicit registry with a *DynamicScenario fallback."""
    registry = {
        "t321_slice": "T321DynamicAScenario",
        "t321_slice_b": "T321DynamicBScenario",
        "t312_slice": "T312DynamicScenario",
        "t311_slice": "T311DynamicScenario",
        "t313_slice": "T313DynamicScenario",
        "t322_slice": "T322DynamicScenario",
        "t323_slice": "T323DynamicScenario",
        "t331_slice": "T331DynamicScenario",
        "t332_slice": "T332DynamicScenario",
        "t333_slice": "T333DynamicScenario",
        "t341_slice": "T341DynamicScenario",
        "t342_slice": "T342DynamicScenario",
        "t343_slice": "T343DynamicScenario",
        "t351_slice": "T351DynamicScenario",
        "t352_slice": "T352DynamicScenario",
        "t353_slice": "T353DynamicScenario",
        "t361_slice": "T361DynamicScenario",
        "t362_slice": "T362DynamicScenario",
        "t363_slice": "T363DynamicScenario",
    }
    attr = registry.get(slice_name)
    if attr and hasattr(module, attr):
        return getattr(module, attr)()
    for attr in dir(module):
        if attr.endswith("DynamicScenario"):
            return getattr(module, attr)()
    raise SystemExit(f"no *DynamicScenario class in {module.__name__}")


def classic_baseline_signatures(suite_id: str) -> dict[str, dict]:
    """Full structural signatures of the frozen classic families of the same suite (read-only
    dedup reference): family_id -> {digest, signature} for near-duplicate detection."""
    version = T332_LOCAL if suite_id == "T332" else BASELINE
    path = BASELINE_DIR / suite_id / version / "cases.jsonl"
    signatures: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            from ioabench.v5.core.case import case_from_dict
            case = case_from_dict(entry)
            sig = signature(case.as_dict())
            signatures.setdefault(case.family_id, {"digest": signature_digest(sig), "signature": sig})
    return signatures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice", required=True, help="dynamic slice module name, e.g. t321_slice")
    parser.add_argument("--families", type=int, default=6)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--run-id", required=True, help="unique run directory name (refused if it exists)")
    args = parser.parse_args()

    module = load_slice(args.slice)
    scenario = slice_scenario(module, args.slice)
    suite_id = scenario.suite_id
    classic_suite_id = suite_id.split("-")[0]  # the frozen classic suite this slice extends
    classic_module = importlib.import_module(f"ioabench.v5.suites.{classic_suite_id.lower()}")
    classic_reference = classic_module.reference_auxiliary() if hasattr(classic_module, "reference_auxiliary") else None
    run_dir = EXPERIMENTAL_DIR / suite_id / args.run_id
    if run_dir.exists():
        print(f"REFUSED: run directory {run_dir} already exists (append-only evidence)", file=sys.stderr)
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    baseline_signatures = classic_baseline_signatures(classic_suite_id)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    family_signatures: dict[str, str] = {}

    pairs = module.generate(seed=args.seed, families=args.families)
    for family_index, (control, risk) in enumerate(pairs):
        pair_id = control.pair_id
        report = check_pair_dynamic(control, risk, scenario=scenario, scorer=module.score,
                                    policies=module.policies(), expected=module.EXPECTED_REFERENCE,
                                    fine_arm_delta=module.fine_arm_delta)
        control_sig = signature(control.as_dict())
        risk_sig = signature(risk.as_dict())
        control_family_digest = family_digest(control.as_dict())
        risk_family_digest = family_digest(risk.as_dict())
        control_digest = signature_digest(control_sig)
        risk_digest = signature_digest(risk_sig)
        # cross-batch near-duplicate detection against the frozen classic families of this suite
        # (stratified: same executable structure across suites is flagged, not auto-merged)
        classic_overlaps = []
        for family_id, ref in baseline_signatures.items():
            delta = structural_delta(control_sig, ref["signature"])
            if delta.get("cross_suite_same_structure"):
                classic_overlaps.append({"family_id": family_id,
                                         "cross_suite_same_structure": True})
            elif delta["same_family"]:
                classic_overlaps.append({"family_id": family_id, "dimensions": delta["dimensions"]})
        if not report["passed"]:
            rejected.append({"pair_id": pair_id, "stage": "dynamic_gates",
                             "failures": report["failures"]})
            continue
        # PERSISTENT cross-run family classification (DEDUP-01): the append-only registry
        # decides new-family vs instance-of-existing vs NO_REFERENCE for this digest
        registry_verdict = classify(FAMILY_REGISTRY, suite_id=classic_suite_id,
                                    digest=control_family_digest)
        if registry_verdict["status"] == "instance_of_existing":
            rejected.append({"pair_id": pair_id, "stage": "cross_run_registry",
                             "failures": [f"family digest already registered as "
                                          f"{registry_verdict['matching_families']}; this pair is a "
                                          f"legitimate instance but NOT a new effective family"]})
            continue
        if control_family_digest in {a["family_digest"] for a in accepted}:
            # same digest within this run: keep as an instance of the just-registered family
            registry_note = "instance of a family accepted in this run"
        else:
            registry_note = registry_verdict["status"]
        # within-run dedup: a NEW family_id matching ANY digest of an earlier family is the
        # rename-only case; instances of the SAME family_id are legitimate reproductions
        prior_family_ids = {fid for fid, metas in family_signatures.items()
                            if any(meta["digest"] == control_digest for meta in metas)}
        if prior_family_ids and control.family_id not in prior_family_ids:
            rejected.append({"pair_id": pair_id, "stage": "within_run_dedup",
                             "failures": [f"structural signature identical to family/families "
                                          f"{sorted(prior_family_ids)} (rename-only, not a new family)"]})
            continue
        family_signatures.setdefault(control.family_id, []).append(
            {"digest": control_digest, "pair_id": pair_id})
        new_family_registered = False
        if registry_verdict["status"] in ("new_family", "NO_REFERENCE"):
            register(FAMILY_REGISTRY, suite_id=classic_suite_id, family_id=control.family_id,
                     digest=control_family_digest, run_id=args.run_id,
                     evidence={"nearest_neighbors": registry_verdict.get("nearest_neighbors", []),
                               "classic_overlaps": classic_overlaps})
            new_family_registered = True
        accepted.append({
            "pair_id": pair_id, "family_index": family_index,
            "control": control.as_dict(), "risk": risk.as_dict(),
            "signatures": {"control": control_digest, "risk": risk_digest},
            "family_digest": control_family_digest,
            "registry_status": registry_verdict["status"],
            "registry_note": registry_note,
            "new_family_registered": new_family_registered,
            "gate_report_digest": hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest(),
            "gate_passed": True,
            "baseline_family_overlaps": classic_overlaps,
            "note": "CANDIDATE_EXPERIMENTAL: not a formal dataset; never enters Gate C/pilot/campaign "
                    "without Gate C/D and a PI decision (PI-V5-007)",
        })

    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "kind": "ioabench.v5.dynamic-experimental-dataset/1",
        "candidate_class": "CANDIDATE_EXPERIMENTAL",
        "slice_module": args.slice, "suite_id": suite_id,
        "scenario_version": getattr(scenario, "version", ""),
        "seed": args.seed, "families_requested": args.families,
        "pairs_accepted": len(accepted), "pairs_rejected": len(rejected),
        "dedup_reference": {"suite": classic_suite_id, "baseline": BASELINE if classic_suite_id != "T332" else T332_LOCAL,
                            "classic_families": len(baseline_signatures),
                            "accepted_with_baseline_overlaps": sum(
                                1 for a in accepted if a["baseline_family_overlaps"])},
        "family_registry": {"path": FAMILY_REGISTRY.relative_to(ROOT).as_posix(),
                            "registry_version": "v5-family-registry-1.0.0"},
        "effective_families_this_run": len({a["family_digest"] for a in accepted}),
        "created_utc": started,
        "authorization_note": "offline deterministic expansion; no provider calls; scaled AI generation "
                              "remains PI_DECISION_REQUIRED (PI-V5-007)",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    with (run_dir / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for entry in accepted:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    with (run_dir / "rejected.jsonl").open("w", encoding="utf-8") as stream:
        for entry in rejected:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    diversity = {
        "family_signature_digests": {fid: [m["digest"] for m in metas]
                                     for fid, metas in family_signatures.items()},
        "distinct_families": len(family_signatures),
        "baseline_family_overlaps": sum(1 for a in accepted if a["baseline_family_overlaps"]),
        "note": "structural-delta dedup within run (all instance digests per family) and against "
                "the frozen baseline families; near-duplicate graph similarity is the M5 "
                "data-factory layer's responsibility",
    }
    (run_dir / "diversity_report.json").write_text(json.dumps(diversity, indent=2, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    print(f"OK suite={suite_id} accepted={len(accepted)} rejected={len(rejected)} -> {run_dir.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
