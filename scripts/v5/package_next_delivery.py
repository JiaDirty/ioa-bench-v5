"""Package the current R13 follow-up with the existing source-review packager; no API calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import package_chatgpt_review as review
from ioabench.runtime.full_manifest import source_tree_hash

BASE_SELECTED = review.selected
NEXT = "artifacts/v5/data_factory/next-r1/"
PROVIDER = "artifacts/v5/provider_contracts/next-r1/"
OFFLINE = "artifacts/v5/data_factory/trials/next-r1-offline-final-r2/"
GOLD = "artifacts/v5/data_factory/quality_controls/df-gold-"
ON_HOST_HISTORY = {"REPORT.json", "RUN_CONTRACT.json", "PROGRESS.json"}


def selected(relative):
    name = relative.as_posix()
    if relative.parts[0] in {".workbuddy-ai", ".zcodeignore", "专利"}:
        return False
    if name.startswith(NEXT + "current_history_probes/"):
        return relative.name in ON_HOST_HISTORY and len(relative.parts) == 6
    return name.startswith((NEXT, PROVIDER, OFFLINE, GOLD)) or BASE_SELECTED(relative)


def main(output):
    evidence = ROOT / NEXT
    acceptance = json.loads((evidence / "FINAL_ACCEPTANCE.json").read_text(encoding="utf-8"))
    runtime = source_tree_hash(ROOT)
    if acceptance["runtime_source_sha256"] != runtime or acceptance["regression"]["status"] != "PASS":
        raise ValueError("Current runtime/final regression is not bound by acceptance")
    review.selected = selected
    review.EVIDENCE = set(review.EVIDENCE) | {NEXT + name for name in (
        "FINAL_ACCEPTANCE.json", "FINAL_ACCEPTANCE.md", "FINAL_REGRESSION.xml",
        "SOURCE_MANIFEST.json", "SHA256SUMS.json", "ALL_USAGE_LEDGER.json",
        "FINAL_REPLAY_VERIFICATION.json", "GENERATED_DATA_PROOFS/INDEX.json")}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = review.main(output, ROOT / "docs/WORK_COMPLETION_20261019_R3.md", snapshot_metadata={
        "kind": "v5_r13_followup_source_and_bounded_evidence_not_formal_release",
        "source_git_head": head, "runtime_source_sha256": runtime,
        "scientific_acceptance": acceptance["status"], "formal_accepted": False,
        "candidate_versions": ["retained historical 5.1.5/5.1.6 candidates", "next-r1 isolated development"],
        "limitations": "Source plus next-r1 generation/repair/panel I/O and runners included. Full historical runner/probe corpus, original archives and credentials stay on host; see EXCLUDED.json and current_history_probes/RUN_CONTRACT.json. History reprobes are current-source projections, not original-source Replay. No scientific acceptance claimed."})
    archive = output.resolve() / result["archive"]
    with tempfile.TemporaryDirectory(prefix="ioa-next-package-") as temporary:
        with zipfile.ZipFile(archive) as stream:
            inventory = json.loads(stream.read(review.pack.META + "FILES.json"))
            stream.extractall(temporary)  # Shared pack.verify already rejected unsafe paths and CRC/SHA mismatches.
        extracted = Path(temporary) / review.pack.PREFIX.rstrip("/")
        for row in inventory:
            if review.pack.digest_file(extracted / row["path"]) != row["sha256"]:
                raise ValueError("Extracted file hash mismatch: " + row["path"])
        if source_tree_hash(extracted) != runtime:
            raise ValueError("Extracted runtime hash mismatch")
    result.update(independent_extraction="PASS", extracted_files_verified=len(inventory),
        extracted_runtime_source_sha256=runtime, source_git_head=head)
    (output / "PACKAGE_VERIFICATION.json").write_bytes(review.pack.json_bytes(result))
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
