from pathlib import Path
import json

import yaml

from ioabench.cli import main
from ioabench.generation.ai_semantic import CandidateValidation
from ioabench.generation.ai_naturalize import GenericNaturalization
from ioabench.generation.validators.semantic import SemanticVerdict
from ioabench.hashing import canonical_sha256


def test_status_prints_milestone_and_ready_work(capsys) -> None:
    assert main(["status"]) == 0
    output = capsys.readouterr().out
    state = yaml.safe_load((Path(__file__).parents[2] / "state" / "PROJECT_STATE.yaml").read_text(encoding="utf-8"))
    assert f"milestone: {state['current_milestone']}" in output
    assert "ready:" in output


def test_validate_spec_passes() -> None:
    assert main(["validate-spec"]) == 0


def test_run_rejects_non_local_profile(capsys) -> None:
    assert main(["run", "--model", "mock", "--suite", "T311", "--profile", "docker"]) == 1
    assert "local-v1" in capsys.readouterr().err


def test_simulation_dataset_generation_labels_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("ioabench.cli.ROOT", tmp_path)
    assert main(["dataset", "generate", "--suite", "T361", "--target", "1"]) == 0
    dataset = tmp_path / "data" / "datasets" / "T361" / "dev-mini"
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generation"]["validity"] == "SIMULATION_ONLY"


def test_version_alias_preserves_candidate_directory() -> None:
    from ioabench.cli import _canonical_version

    assert _canonical_version("v1.0.0") == "1.0.0"
    assert _canonical_version("v1-candidates") == "v1-candidates"


def test_formal_generation_writes_hashed_semantic_evidence(tmp_path, monkeypatch) -> None:
    async def validate_candidates(records, *, primary_model, secondary_model, cache_path):
        return [
            CandidateValidation(
                record["candidate_id"], True,
                tuple(SemanticVerdict(model_id, "ACCEPT", 1.0, ("task",), {"model_id": model_id}) for model_id in (primary_model, secondary_model)),
            )
            for record in records
        ]

    monkeypatch.setattr("ioabench.cli.ROOT", tmp_path)
    monkeypatch.setattr("ioabench.generation.ai_semantic.validate_candidates", validate_candidates)
    async def naturalize_candidates(skeletons, *, model_id, cache_path):
        return ({skeleton.candidate_id: GenericNaturalization(skeleton.candidate_id, "input", "context", "message", model_id, "output", {}, None) for skeleton in skeletons}, [])
    monkeypatch.setattr("ioabench.generation.ai_naturalize.naturalize_candidates", naturalize_candidates)
    assert main(["dataset", "generate", "--suite", "T312", "--target-qualified", "1", "--profile", "formal-v1"]) == 0
    path = tmp_path / "data" / "datasets" / "T312" / "v1-candidates"
    semantic = json.loads((path / "semantic-validation.json").read_text(encoding="utf-8"))
    case = json.loads((path / "cases.jsonl").read_text(encoding="utf-8").splitlines()[0])
    evidence = next(item for item in semantic["results"] if item["candidate_id"] == case["candidate_id"])
    assert evidence["input_sha256"] == canonical_sha256(case["sut_payload"])
    assert semantic["content_sha256"] == canonical_sha256({key: value for key, value in semantic.items() if key != "content_sha256"})
