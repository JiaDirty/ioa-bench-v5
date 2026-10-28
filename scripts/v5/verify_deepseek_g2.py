"""Read-only terminal resume and strict Replay under each retained source revision."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_revision(out, source):
    sys.path.insert(0, str(source / "src"))
    from ioabench.hashing import canonical_sha256
    from ioabench.models import ModelProfile
    from ioabench.runtime.full_manifest import source_tree_hash
    from ioabench.v5 import evaluation
    from ioabench.v5.ai_generation.direct_deepseek import candidate_result, generate_candidate
    from ioabench.v5.replay import replay_case
    from ioabench.models import deepseek, aihubmix

    runtime = source_tree_hash(source)
    assert runtime == source.name, "retained source identity differs"
    network_attempts = []
    loopback_connections = []
    original_connect = socket.socket.connect

    def forbidden_http(*args, **kwargs):
        network_attempts.append(True)
        raise AssertionError("network forbidden during Replay/resume")

    def forbidden_connect(sock, address):
        # Windows asyncio builds its internal socketpair over loopback.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            loopback_connections.append(True)
            return original_connect(sock, address)
        return forbidden_http()

    deepseek.urlopen = aihubmix.urlopen = forbidden_http
    socket.socket.connect = forbidden_connect

    class ClosedStudy:
        def __init__(self):
            self.out, self.stop = out, out / "STOP.json"

        async def invoke(self, *args, **kwargs):
            raise AssertionError("terminal generation attempted a provider call")

    indices, results = {}, []
    for path in sorted((out / "candidates").glob("*/RESULT.json")):
        directory = path.parent
        manifest = read(directory / "MANIFEST.json")
        if manifest["source_sha256"] != runtime:
            continue
        result = candidate_result(directory)
        if result["status"] != "PASS":
            continue
        before = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*")
                  if p.is_file() and not p.name.endswith(".lock")}
        history_id = manifest["history_sha256"]
        if history_id not in indices:
            for history in (out / "history").glob("*.json"):
                index = read(history)
                if canonical_sha256(index) == history_id:
                    indices[history_id] = index
                    break
        assert history_id in indices, "pinned history unavailable"
        resumed = asyncio.run(generate_candidate(ClosedStudy(), result["task"], indices[history_id], [], workspace=source))
        assert resumed == result, "terminal resume changed result"
        checks, resumed_batches = [], 0
        for pinned in sorted((directory / "strict/artifacts/v5/evaluations").glob("*/manifest.json")):
            m = read(pinned)
            assert m["source_sha256"] == runtime
            for row in evaluation.read_results(pinned.parent):
                check = replay_case(directory / "strict", m["run_id"], row["case_id"])
                assert check["passed"] and check["provider_calls"] == 0
                checks.append(check)
            # Resume a disposable copy so report/checkpoint refresh cannot mutate sealed evidence.
            with tempfile.TemporaryDirectory(prefix="ioa-g2-resume-") as temporary:
                copied = Path(temporary)
                shutil.copytree(directory / "strict", copied / "strict")
                copied_run = copied / "strict/artifacts/v5/evaluations" / m["run_id"]
                old_rows = evaluation.read_results(copied_run)
                evaluation.run_batch(copied / "strict", directory / "CASES.jsonl", run_id=m["run_id"],
                    profile=ModelProfile(**m["profile"]), parameters=m["parameters"],
                    reference_policy=m["reference_policy"], expected_identity=m["expected_identity"],
                    max_attempts=m["max_attempts"], resume=True)
                assert evaluation.read_results(copied_run) == old_rows, "resume appended terminal results"
                resumed_batches += 1
        after = {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*")
                 if p.is_file() and not p.name.endswith(".lock")}
        assert before == after and candidate_result(directory) == result, "Replay/resume changed evidence"
        results.append({"candidate": result["task"]["id"], "status": "PASS", "runtime_sha256": runtime,
                        "strict_replays": checks, "terminal_generation_resume": "PASS",
                        "reference_batch_resumes": resumed_batches, "sealed_bytes_unchanged": True})
    assert not network_attempts
    return {"runtime_sha256": runtime, "status": "PASS", "candidates": results, "provider_calls": 0,
            "external_connection_or_provider_http_attempts": len(network_attempts),
            "windows_asyncio_loopback_connections": len(loopback_connections)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.source:
        result = verify_revision(out, args.source.resolve())
    else:
        ledger_before = sha(out / "REQUEST_LEDGER.jsonl")
        revisions = sorted({read(p.parent / "MANIFEST.json")["source_sha256"]
                            for p in (out / "candidates").glob("*/RESULT.json") if read(p)["status"] == "PASS"})
        reports = []
        with tempfile.TemporaryDirectory(prefix="ioa-g2-verification-") as temporary:
            for revision in revisions:
                child_result = Path(temporary) / (revision + ".json")
                subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--out", str(out),
                    "--source", str(out / "source_revisions" / revision), "--result", str(child_result)], check=True)
                reports.append(read(child_result))
        assert sha(out / "REQUEST_LEDGER.jsonl") == ledger_before
        result = {"status": "PASS", "revisions": reports, "provider_calls": 0,
                  "ledger_unchanged": True, "candidate_count": sum(len(r["candidates"]) for r in reports),
                  "strict_replay_count": sum(len(c["strict_replays"]) for r in reports for c in r["candidates"])}
        cli = read(out / "CLI_NO_RESEND.json")
        assert cli["status"] == "PASS" and cli["provider_calls"] == cli["cli_result"]["result"]["started"] == 0
        result["all_terminal_cli_reentry"] = cli
    destination = args.result or out / "REPLAY_RESUME.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"revisions", "candidates"}}), flush=True)


if __name__ == "__main__":
    main()
