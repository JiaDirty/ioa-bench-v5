from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _module():
    path = ROOT / "scripts/v4_1_7_finalize_campaign.py"
    spec = importlib.util.spec_from_file_location("v4_1_7_finalize_campaign", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path, module) -> tuple[dict, Path]:
    for name, content in (("AGENTS.md", "fixture\n"), ("pyproject.toml", "[project]\nname='fixture'\n"),
                          ("data/datasets/DATASET_PACK_v4.yaml", "pack: DATASET_PACK_v4\n"),
                          ("scripts/v4_1_7_finalize_campaign.py", "# fixture\n")):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    release = {"release_id": "v4.1.7-corrective-integration-20261002", "source_tree_sha256": "a" * 64,
               "dataset_pack_v4_sha256": "b" * 64,
               "invalid_output_semantics": {"strict_retry_semantics": True}, "datasets": {}}
    rows = []
    for suite in module.SUITES:
        version = "2.0.0"
        cases = [{"candidate_id": f"{suite}-{index:03d}"} for index in range(90)]
        dataset_dir = tmp_path / "data/datasets" / suite / version
        dataset_dir.mkdir(parents=True)
        cases_path = dataset_dir / "cases.jsonl"
        cases_path.write_text("".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8")
        dataset_manifest = {"suite": suite, "version": version, "content_sha256": None}
        content_hash = module.canonical_hash({"manifest": dataset_manifest, "cases": cases})
        dataset_manifest["content_sha256"] = content_hash
        manifest_path = dataset_dir / "manifest.json"
        _write(manifest_path, dataset_manifest)
        release["datasets"][suite] = {"version": version, "content_sha256": content_hash,
                                      "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    release_path = tmp_path / "release/BENCHMARK_RELEASE_v4.1.7-corrective-integration-20261002.json"
    _write(release_path, release)
    release_sha = hashlib.sha256(release_path.read_bytes()).hexdigest()
    for suite in module.SUITES:
        run_id = f"deepseek-v4.1-flash-{suite}-2.0.0-v4.1-formal"
        run_dir = tmp_path / "data/runs" / run_id
        results = {}
        for index in range(90):
            case_id = f"{suite}-{index:03d}"
            replay = {"model_records": [], "scenario": {}}
            if suite == "T353":
                replay["scenario"]["paired_runs"] = {mode: {"replay": {"branch": mode}}
                                                        for mode in ("honest", "manipulated")}
            replay["content_sha256"] = module.canonical_hash(replay)
            journal_path = run_dir / "attempts" / case_id / "attempt-1.jsonl"
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            journal_path.write_text(json.dumps({"kind": "attempt", "attempt_no": 1, "case_id": case_id}) + "\n", encoding="utf-8")
            journal = {"path": journal_path.relative_to(tmp_path).as_posix(),
                       "sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest()}
            attempt = {"attempt_no": 1, "status": "COMPLETED", "model_records_produced": 0,
                       "valid_model_behavior_observed": True, "infrastructure_failure": False,
                       "attempt_journal": journal}
            results[str(index)] = {"case_id": case_id, "suite": suite, "status": "COMPLETED",
                                   "difficulty": "easy", "score": {"outcome_class": "EARLY_SAFE", "task_utility": True},
                                   "replay": replay, "attempt_no": 1, "attempts": [attempt],
                                   "attempt_journal": journal}
        _write(run_dir / "results.json", results)
        manifest = {"run_id": run_id, "runtime": {"simulation_only": suite in module.SIMULATION_ONLY},
                    "release": {"release_id": release["release_id"], "release_sha256": release_sha,
                                "source_tree_sha256": release["source_tree_sha256"]}}
        frozen = tmp_path / "data/runs/_v4_1_7_manifests" / f"{run_id}.manifest.json"
        runtime = run_dir / "manifest" / f"{run_id}.json"
        _write(frozen, manifest)
        runtime.parent.mkdir(parents=True)
        runtime.write_bytes(frozen.read_bytes())
        rows.append({"suite": suite, "run_id": run_id, "binding_level": "STRICT_BINDING",
                     "canonical_accepted": True, "provider_model_records": 0})
    audit = {"release_id": release["release_id"], "release_sha256": release_sha,
             "source_tree_sha256": release["source_tree_sha256"], "pass": True,
             "verdict": "STRICT_18_OF_18", "historical_runs_consumed": 0,
             "strict_count": 18, "total_suites": 18, "suites": rows}
    audit_path = tmp_path / "artifacts/binding.json"
    _write(audit_path, audit)
    return audit, audit_path


def test_finalizer_rejects_non_strict_audit():
    module = _module()
    release = {"release_id": "r", "source_tree_sha256": "s"}
    with pytest.raises(ValueError, match="STRICT_18_OF_18"):
        module.assert_audit({"release_id": "r", "release_sha256": "h", "source_tree_sha256": "s",
                             "pass": False, "verdict": "NOT_STRICT"}, release, "h")


def test_finalizer_builds_complete_delivery_from_strict_fixture(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    audit, audit_path = _fixture(tmp_path, module)
    output = tmp_path / "artifacts/final"
    bundle = tmp_path / "artifacts/ioa-v4.1.7.zip"
    monkeypatch.setattr(module, "source_tree_hash", lambda: "a" * 64)
    monkeypatch.setattr(sys, "argv", ["v4_1_7_finalize_campaign.py", "--binding-audit", str(audit_path),
                                      "--output-directory", str(output), "--bundle-path", str(bundle)])
    assert module.main() == 0
    campaign = json.loads((output / "campaign.json").read_text(encoding="utf-8"))
    acceptance = json.loads((output / "final-project-acceptance.json").read_text(encoding="utf-8"))
    delivery = json.loads((output / "delivery-manifest.json").read_text(encoding="utf-8"))
    assert campaign["cases"] == 1620
    assert campaign["historical_runs_consumed"] == 0
    assert campaign["suite_results"]["T361"]["SIMULATION_ONLY"] is True
    assert acceptance["pass"] is True and acceptance["delivery"]["sha256"] == module.sha256(output / "delivery-manifest.json")
    assert delivery["crc_verified"] is True and bundle.is_file()

