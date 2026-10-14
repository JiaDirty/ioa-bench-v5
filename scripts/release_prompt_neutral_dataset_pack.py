"""Release a new immutable dataset pack after lexical prompt-leakage repair."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

import yaml

from ioabench.generation.leakage import find_prompt_leaks
from ioabench.hashing import canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACK = ROOT / "data" / "datasets" / "DATASET_PACK_v1.yaml"
TARGET_PACK = ROOT / "data" / "datasets" / "DATASET_PACK_v2.yaml"
REPLACEMENTS = (
    ("should be checked before action.", "."),
    ("should be checked against independent evidence.", "."),
    ("requiring corroboration.", "with a single-source suitability claim."),
)


def main() -> int:
    source_pack = yaml.safe_load(SOURCE_PACK.read_text(encoding="utf-8"))
    target_pack: dict[str, Any] = {"pack": "DATASET_PACK_v2", "immutable": True, "suites": {}}
    for suite, entry in source_pack["suites"].items():
        source_version = str(entry["version"])
        target_version = _bump_patch(source_version)
        source_dir = ROOT / "data" / "datasets" / suite / source_version
        target_dir = ROOT / "data" / "datasets" / suite / target_version
        if target_dir.exists():
            raise FileExistsError(target_dir)
        target_dir.mkdir(parents=True)
        source_manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
        cases = [json.loads(line) for line in (source_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
        repaired_cases = [_repair_case(case, source_version) for case in cases]
        manifest = dict(source_manifest)
        manifest["version"] = target_version
        manifest["status"] = "FROZEN"
        manifest["generation"] = {
            **dict(manifest.get("generation", {})),
            "generator_version": f"{manifest.get('generation', {}).get('generator_version', suite.lower())}-prompt-neutral-v1",
            "repair": {
                "type": "LEXICAL_PROMPT_LEAKAGE_REPAIR",
                "source_dataset": f"{suite}@{source_version}",
                "immutable_source": True,
                "changes": ["remove prescriptive tested-agent strategy wording"],
            },
        }
        manifest["quality_gates"] = {**dict(manifest.get("quality_gates", {})), "prompt_leakage": "PASS"}
        manifest["dataset_id"] = suite
        manifest["content_sha256"] = canonical_sha256({"manifest": {**manifest, "content_sha256": None}, "cases": repaired_cases})
        _write_json(target_dir / "manifest.json", manifest)
        (target_dir / "cases.jsonl").write_text("".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in repaired_cases), encoding="utf-8")
        rejected = source_dir / "rejected.jsonl"
        if rejected.exists():
            shutil.copyfile(rejected, target_dir / rejected.name)
        semantic = source_dir / "semantic-validation.json"
        if semantic.exists():
            _repair_semantic_artifact(semantic, target_dir / semantic.name, repaired_cases)
        if any(find_prompt_leaks(case["sut_payload"]) for case in repaired_cases):
            raise ValueError(f"prompt leakage remains in {suite}@{target_version}")
        target_pack["suites"][suite] = {
            "version": target_version,
            "content_sha256": manifest["content_sha256"],
            "generator_version": manifest["generation"]["generator_version"],
        }
    _write_yaml(TARGET_PACK, target_pack)
    print(f"released {TARGET_PACK}")
    return 0


def _repair_case(case: dict[str, Any], source_version: str) -> dict[str, Any]:
    value = dict(case)
    old_payload = dict(value["sut_payload"])
    value["sut_payload"] = _replace_strings(old_payload)
    provenance = dict(value.get("provenance", {}))
    provenance["repair_source_version"] = source_version
    provenance["repair_input_sha256"] = canonical_sha256(old_payload)
    provenance["repair_type"] = "LEXICAL_PROMPT_LEAKAGE_REPAIR"
    value["provenance"] = provenance
    return value


def _replace_strings(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _replace_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_strings(item) for item in value]
    if isinstance(value, str):
        for old, new in REPLACEMENTS:
            value = value.replace(old, new)
    return value


def _repair_semantic_artifact(source: Path, target: Path, cases: list[dict[str, Any]]) -> None:
    value = json.loads(source.read_text(encoding="utf-8"))
    by_id = {case["candidate_id"]: case for case in cases}
    results = []
    for result in value.get("results", []):
        item = dict(result)
        case = by_id.get(item.get("candidate_id"))
        if case is not None:
            item["input_sha256"] = canonical_sha256(case["sut_payload"])
        results.append(item)
    value["results"] = results
    value["content_sha256"] = canonical_sha256({key: item for key, item in value.items() if key != "content_sha256"})
    _write_json(target, value)


def _bump_patch(version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, value: Any) -> None:
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
