"""Build a source-focused review ZIP; reuse the workspace packager's integrity checks."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import os
import zipfile

import package_workspace_snapshot as pack

ROOT = pack.ROOT
TOPS = {"src", "tests", "scripts", "contracts", "config", "roles", "scenarios", "worlds",
        "prompts", "templates", "adr", "docs", "state", "NightGoalDoc"}
EVIDENCE = {
    "artifacts/workspace_maintenance/20261010/offline-matrix.json",
    "artifacts/workspace_maintenance/20261010/tests.json",
    "artifacts/workspace_maintenance/20261010/cleanup.json",
    "artifacts/workspace_maintenance/20261010/final-verification.json",
    "artifacts/v5/gates/offline-matrix-20261009-single-model-precheck.json",
    "artifacts/v5/data_quality/5.1.5-candidate-20261006/report.json",
    "artifacts/v5/data_quality/5.1.6-candidate-20261009/report.json",
    "artifacts/v5/pilot/pilot-20261006-v5.1.5/gate_e.json",
    "artifacts/v5/pilot/pilot-20261006-v5.1.5/deepseek_single_model_diagnostic.json",
    "artifacts/v5/pilot/pilot-20261006-v5.1.5/deepseek_single_model_diagnostic.md",
    "artifacts/scientific_validity_audit_20261004/machine_summary.json",
    "artifacts/scientific_validity_audit_20261004/EVIDENCE_LEDGER.json",
}
REVIEW = "artifacts/v5/data_factory/review/process-audit-20261014-r1"
EVIDENCE.update(f"{REVIEW}/{name}" for name in (
    "REPORT.md", "MORNING_REPORT.md", "AUDIT_VERIFICATION.json", "CAPABILITY_INVENTORY.json",
    "HANDOFF_CHECK.json", "FIX.diff", "PYTEST_ALL_FOCUSED.xml", "PYTEST_V5.xml",
    "offline_all18/PREFLIGHT.json"))
EVIDENCE.update(f"artifacts/v5/provider_contracts/pi-order-20261014T082638/{name}"
                for name in ("REPORT.md", "VERIFICATION.json"))
EXAMPLE = "artifacts/v5/data_factory/trials/pi-order-gpt-sol-20261014-r2/candidate-01"
EVIDENCE.update(f"{EXAMPLE}/{name}" for name in (
    "MANIFEST.json", "GENERATOR_REQUEST.json", "GENERATOR_RESPONSE.json", "BLUEPRINT.json",
    "PAIR.json", "HARD_GATE.json", "FIDELITY.json", "REFERENCE_RESULTS.json", "DIVERSITY.json",
    "REVIEW_INPUT.json", "AUDITOR_REQUEST.json", "AUDITOR_RESPONSE.json", "REVIEW.json", "RESULT.json"))
EVIDENCE.update({
    "artifacts/v5/manual_18/20261013-authored-contract-fix-r1/cases.jsonl",
    "artifacts/v5/manual_18/20261013-authored-scientific-r3/cases.jsonl",
    "artifacts/v5/manual_18/20261013-authored-scientific-r3/execution_profile.py",
    "artifacts/v5/dynamic_world/suite-evidence-matrix.json",
    "artifacts/v5/dynamic_world/suite-structure-scan.json",
    "data/v5/dynamic_experimental/T321-DYNA/m8-fill-20261011-t321/manifest.json",
    "data/v5/dynamic_experimental/T321-DYNA/m8-fill-20261011-t321/cases.jsonl",
})


def selected(relative):
    parts = relative.parts
    if len(parts) == 1 or parts[0] in TOPS:
        return True
    if parts[0] == "release" and len(parts) == 2 and relative.suffix == ".json":
        return True
    if relative.as_posix() in EVIDENCE:
        return True
    return (len(parts) >= 5 and parts[:3] == ("data", "v5", "datasets")
            and parts[4] in {"5.1.5-candidate-20261006", "5.1.6-candidate-20261009"})


def main(output, handoff, *, snapshot_metadata=None):
    output = output.resolve()
    if not output.is_relative_to((ROOT / "exports").resolve()):
        raise ValueError("Output must be a new directory under workspace exports/")
    handoff = handoff.resolve()
    if not handoff.is_relative_to(ROOT.resolve()) or not handoff.is_file():
        raise ValueError("Handoff must be an existing workspace file")
    handoff_relative = handoff.relative_to(ROOT.resolve()).as_posix()
    output.mkdir(parents=True, exist_ok=False)
    included, excluded = [], []
    for base, dirs, names in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if d not in pack.SKIP_DIRS and (Path(base) / d).relative_to(ROOT).parts[0] not in {"exports", "archive"}]
        for d in dirs:
            p = Path(base) / d
            assert not p.is_symlink() and not p.is_junction(), "Linked directory rejected"
        for name in names:
            path = Path(base) / name
            relative = path.relative_to(ROOT)
            assert not path.is_symlink(), "Linked file rejected"
            reason = None
            if name.startswith(".env") and not name.endswith((".example", ".sample", ".template")):
                reason = "local_credentials"
            elif path.suffix.lower() in {".pem", ".p12", ".pfx", ".key", ".pyc", ".pyo"}:
                reason = "credential_or_regenerable_bytecode"
            elif path.suffix.lower() in pack.ARCHIVES:
                reason = "historical_archive_retained_on_host"
            elif not selected(relative):
                reason = "outside_source_review_scope_retained_on_host"
            if reason:
                excluded.append({"path": relative.as_posix(), "reason": reason})
            else:
                included.append(path)
    included.sort()
    paths = {p.relative_to(ROOT).as_posix() for p in included}
    assert EVIDENCE <= paths, "Required evidence missing"
    assert all(f"src/ioabench/v5/suites/t{n}.py" in paths for n in (311,312,313,321,322,323,331,332,333,341,342,343,351,352,353,361,362,363))
    assert handoff_relative in paths and ".env" not in paths
    secrets = pack.local_secrets()
    archive = output / ("IoA-Bench-" + output.name + ".zip")
    temporary = archive.with_suffix(".zip.partial")
    inventory = []
    with zipfile.ZipFile(temporary, "x", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in included:
            before = p.stat()
            content = p.read_bytes()
            assert not any(s in content for s in secrets) and not pack.KEY_TOKEN.search(content) and not pack.PRIVATE_KEY.search(content), f"Credential detected; value suppressed: {p.relative_to(ROOT)}"
            after = p.stat()
            assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), "Concurrent change"
            import hashlib
            inventory.append({"path": p.relative_to(ROOT).as_posix(), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
            z.writestr(pack.PREFIX + p.relative_to(ROOT).as_posix(), content)
        # Confirm included files still match the snapshot before publishing it.
        assert all(pack.digest_file(ROOT / r["path"]) == r["sha256"] for r in inventory)
        snapshot = {"kind": "source_review_not_formal_release_or_full_replay", "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "read_first": handoff_relative, "provider_calls": 0,
                    "source_scope": sorted(TOPS), "candidate_versions": ["5.1.5-candidate-20261006", "5.1.6-candidate-20261009 (T332 only)"],
                    "limitations": "Historical full runs, backups, reviewer sealed keys, credentials, caches and archives omitted except explicitly selected review evidence/example; consult EXCLUDED.json. Partial example evidence is not a full replay bundle. No scientific acceptance claimed.",
                    "secret_scan": "Known local .env secret values, key-token patterns and private-key headers checked."}
        snapshot.update(snapshot_metadata or {})
        for name, value in (("FILES.json", inventory), ("EXCLUDED.json", excluded), ("SNAPSHOT.json", snapshot)):
            z.writestr(pack.META + name, pack.json_bytes(value))
    result = pack.verify(temporary)
    temporary.rename(archive)
    result.update({"archive": archive.name, "bytes": archive.stat().st_size, "sha256": pack.digest_file(archive), "secret_scan": "PASS", "provider_calls": 0})
    (output / "PACKAGE_VERIFICATION.json").write_bytes(pack.json_bytes(result))
    (output / (archive.name + ".sha256")).write_text(result["sha256"] + "  " + archive.name + "\n", encoding="ascii")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.handoff)
