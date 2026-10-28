"""Package the isolated G2 run, exact runtimes and bound historical inputs; never call a provider."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import package_workspace_snapshot as pack
from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.evaluation import writer_lock


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def selection(out):
    files = set()
    for folder in ("src", "contracts", "config", "scripts", "tests", "state"):
        files.update(p for p in (ROOT / folder).rglob("*") if p.is_file())
    review = ROOT / "artifacts/v5/data_factory/coord-round01-20261019T073200Z/REVIEW_PACKAGE_FOR_HUMANS"
    files.update(p for p in review.rglob("*") if p.is_file())
    files.update(p for p in out.rglob("*") if p.is_file())
    for name in ("AGENTS.md", "README.md", "pyproject.toml", "uv.lock", "requirements.txt",
                 "docs/v5/V5_PI_DECISION_LOG.md", "docs/v5/V5_DEEPSEEK_DIRECT_CALL_CONTRACT_20261013.md"):
        if (ROOT / name).is_file():
            files.add(ROOT / name)
    prior = ROOT / "artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z/HISTORY_INDEX_V3.json"
    files.add(prior)
    for index in [prior, *(out / "history").glob("*.json")]:
        for name, expected in read(index)["source_sha256"].items():
            path = (ROOT / name).resolve()
            assert path.is_relative_to(ROOT) and pack.digest_file(path) == expected, "bound history changed"
            files.add(path)
    selected = []
    for path in sorted(files):
        relative = path.relative_to(ROOT)
        if (any(part in pack.SKIP_DIRS for part in relative.parts) or path.suffix in {".pyc", ".pyo"}
                or path.name.endswith(".lock") and path.name != "uv.lock"):
            continue
        assert not path.is_symlink() and not path.name.startswith(".env"), "credential/link cannot be packaged"
        selected.append(path)
    return selected


def build(out, output, name):
    assert out.is_relative_to(ROOT / "artifacts/v5/data_factory/direct_deepseek_g2")
    assert output.is_relative_to(ROOT / "exports")
    assert Path(name).name == name and name.endswith(".zip")
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / name
    temporary = archive_path.with_suffix(".zip.partial")
    assert not archive_path.exists() and not temporary.exists(), "package output is immutable"
    files, secrets = selection(out), pack.local_secrets()
    nested_review_archives = 0
    for path in files:
        if path.suffix.lower() != ".zip":
            continue
        assert path.name.startswith("SEND_reviewer_"), "unexpected nested archive"
        with zipfile.ZipFile(path) as nested:
            for member in nested.infolist():
                data = nested.read(member)
                assert not Path(member.filename).name.startswith(".env")
                if any(secret in data for secret in secrets) or pack.KEY_TOKEN.search(data) or pack.PRIVATE_KEY.search(data):
                    raise ValueError("credential in nested reviewer material; value suppressed")
        nested_review_archives += 1
    inventory, stats = [], {}
    with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for i, path in enumerate(files, 1):
            relative = path.relative_to(ROOT).as_posix()
            before = path.stat()
            stats[relative] = (before.st_size, before.st_mtime_ns)
            digest, tail = hashlib.sha256(), b""
            with path.open("rb") as source, archive.open(pack.PREFIX + relative, "w", force_zip64=True) as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    sample = tail + chunk
                    if any(secret in sample for secret in secrets) or pack.KEY_TOKEN.search(sample) or pack.PRIVATE_KEY.search(sample):
                        raise ValueError("credential scan failed; value suppressed: " + relative)
                    digest.update(chunk)
                    target.write(chunk)
                    tail = sample[-4096:]
            after = path.stat()
            assert (after.st_size, after.st_mtime_ns) == stats[relative], "file changed during packaging"
            inventory.append({"path": relative, "bytes": before.st_size, "sha256": digest.hexdigest()})
            if i % 2000 == 0:
                print(json.dumps({"phase": "package", "files": i, "total": len(files)}), flush=True)
        for path in files:
            stat = path.stat()
            assert (stat.st_size, stat.st_mtime_ns) == stats[path.relative_to(ROOT).as_posix()]
        metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "kind": "DEVELOPMENT_EXPLORATORY_SAME_FAMILY",
            "provider_calls": 0, "formal_accepted": False, "read_first": out.relative_to(ROOT).as_posix() + "/ROUND_REPORT.md",
            "excluded": "credentials, git database, caches, unrelated user untracked files and unbound historical archives",
            "historical_scope": "all raw inputs and adjacent results referenced by each retained history index; all old history remains on host"}
        for filename, value in (("FILES.json", inventory), ("EXCLUDED.json", metadata["excluded"]), ("SNAPSHOT.json", metadata)):
            archive.writestr(pack.META + filename, pack.json_bytes(value))
    print(json.dumps({"phase": "verify_crc_members_and_sha256", "files": len(files)}), flush=True)
    verification = pack.verify(temporary)
    with tempfile.TemporaryDirectory(prefix="ioa-g2-handoff-") as extraction:
        extracted = Path(extraction)
        with zipfile.ZipFile(temporary) as archive:
            archive.extractall(extracted)
        root = extracted / "ioa_codex_spec"
        assert source_tree_hash(root) == source_tree_hash(ROOT), "extracted authoritative runtime differs"
        revisions = root / out.relative_to(ROOT) / "source_revisions"
        for revision in revisions.iterdir():
            assert source_tree_hash(revision) == revision.name, "retained source revision incomplete"
        replay_result = output / (archive_path.stem + "-EXTRACTED_REPLAY.json")
        subprocess.run([sys.executable, "-B", str(root / "scripts/v5/verify_deepseek_g2.py"), "--out",
            str(root / out.relative_to(ROOT)), "--result", str(replay_result)], cwd=root, check=True)
        replay = read(replay_result)
        assert replay["status"] == "PASS" and replay["provider_calls"] == 0
    temporary.rename(archive_path)
    verification.update(status="PASS", archive=archive_path.name, sha256=pack.digest_file(archive_path),
        bytes=archive_path.stat().st_size, secret_scan="PASS", extracted_runtime_sha256=source_tree_hash(ROOT),
        all_retained_revision_hashes_match=True, extracted_strict_replays=replay["strict_replay_count"],
        extracted_terminal_resumes=replay["candidate_count"], nested_review_archives_scanned=nested_review_archives, provider_calls=0)
    (output / (archive_path.stem + "-VERIFICATION.json")).write_bytes(pack.json_bytes(verification))
    (output / (archive_path.name + ".sha256")).write_text(verification["sha256"] + "  " + archive_path.name + "\n", encoding="ascii")
    print(json.dumps(verification, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive-name", required=True)
    args = parser.parse_args()
    with writer_lock(ROOT / "artifacts/v5/data_factory"), writer_lock(args.out.resolve()):
        build(args.out.resolve(), args.output.resolve(), args.archive_name)
