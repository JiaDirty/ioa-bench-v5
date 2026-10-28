from __future__ import annotations

import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
import zipfile

import pytest

from ioabench.hashing import canonical_sha256

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/v5/package_development_factory.py"
spec = importlib.util.spec_from_file_location("package_development_factory_test", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


@pytest.fixture
def handoff(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    def write(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(package.pack.json_bytes(value))
        return path
    raw = write("data/historical.json", {"world": "original"})
    manifest = write("candidates/valid/MANIFEST.json", {"source_sha256": "pinned-runtime"})
    row = {"status": "PASS", "formal_accepted": False,
           "evidence_sha256": {"MANIFEST.json": package.pack.digest_file(manifest)}}
    result = write("candidates/valid/RESULT.json", row)
    terminal = write("candidates/valid/TERMINAL.json", {"result_sha256": canonical_sha256(row), "result": row})
    history = write("history.json", {"source_sha256": {"data/historical.json": package.pack.digest_file(raw)}})
    packet = write("reviews/one/AUDIT_PACKET.json", {"source_binding": {
        "directory": str(tmp_path / "candidates/valid"), "files": {
            path.name: package.pack.digest_file(path) for path in (manifest, result, terminal)}}})
    files = [raw, manifest, result, terminal, history, packet]
    snapshot = {"kind": "DEVELOPMENT_AUTO_AUDITED", "original_workspace": str(tmp_path),
                "bound_history_indexes": ["history.json"], "sealed_candidate_directories": ["candidates/valid"]}
    return files, snapshot


def test_smoke_crc_sha_members_history_candidate_and_audit_bindings(tmp_path, handoff):
    files, snapshot = handoff
    archive = tmp_path / "smoke.zip"
    package.write_archive(archive, files, {"handoff/GIT_DIFF.patch": b"diff --git a/src/a.py b/src/a.py\n"}, snapshot, ())
    verified = package.verify_archive(archive)
    assert verified["all_entry_crc_checked_during_read"] and verified["all_file_sha256_match"]
    assert verified["historical_source_bindings"] == verified["candidate_seals"] == verified["audit_source_bindings"] == "PASS"
    assert verified["file_count"] == len(files) + 1 and verified["provider_calls"] == 0
    with zipfile.ZipFile(archive) as zipped:
        assert all(name.startswith("ioa_codex_spec/") for name in zipped.namelist())


def test_missing_historical_raw_member_rejected_even_with_consistent_zip_inventory(tmp_path, handoff):
    files, snapshot = handoff
    archive = tmp_path / "incomplete.zip"
    package.write_archive(archive, files[1:], {}, snapshot, ())
    with pytest.raises(ValueError, match="bound archive evidence"):
        package.verify_archive(archive)


def test_extra_member_rejected_by_exact_inventory(tmp_path, handoff):
    files, snapshot = handoff
    archive = tmp_path / "membership.zip"
    package.write_archive(archive, files, {}, snapshot, ())
    with zipfile.ZipFile(archive, "a") as zipped:
        zipped.writestr("ioa_codex_spec/unlisted.txt", "unexpected")
    with pytest.raises(ValueError, match="membership differs"):
        package.verify_archive(archive)


def test_exact_environment_secret_and_key_patterns_blocked_with_value_suppressed(tmp_path, handoff):
    files, snapshot = handoff
    secret = b"private-development-value-123456789"
    for ordinal, (data, secrets) in enumerate(((secret, (secret,)), (b"sk-" + b"x" * 24, ()))):
        with pytest.raises(ValueError, match="value suppressed") as error:
            package.write_archive(tmp_path / (str(ordinal) + ".zip"), files,
                                  {"handoff/unsafe.txt": data}, snapshot, secrets)
        assert data.decode() not in str(error.value)


def test_nested_archive_secret_and_unsafe_paths_are_rejected():
    buffer = BytesIO()
    secret = b"private-development-value-123456789"
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as nested:
        nested.writestr("payload.txt", secret)
    with pytest.raises(ValueError, match="value suppressed"):
        package.scan_blob(buffer.getvalue(), "nested.zip", (secret,))
    for name in ("../outside", "C:/outside", "/outside", "a\\b"):
        with pytest.raises(ValueError, match="unsafe"):
            package.safe_path(name)


def test_credentials_and_cache_are_excluded_from_explicit_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    assert not package.selected_file(tmp_path / ".env")
    assert not package.selected_file(tmp_path / "config/private.key")
    assert not package.selected_file(tmp_path / "src/__pycache__/file.pyc")
    assert package.selected_file(tmp_path / "uv.lock")


def test_windows_absolute_source_binding_relocates_without_host_access():
    assert package.workspace_relative("D:/Project/ioa_codex_spec/artifacts/old/PAIR.json",
                                      "D:/Project/ioa_codex_spec") == "artifacts/old/PAIR.json"
    with pytest.raises(ValueError):
        package.workspace_relative("D:/Other/PAIR.json", "D:/Project/ioa_codex_spec")


def test_selection_includes_only_bound_paid_ledger_catalog_and_recursive_reuse_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    monkeypatch.setattr(package.subprocess, "check_output", lambda *args, **kwargs: b"")
    def write(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path
    source = "old/candidates/replayed"
    paid = "older/candidates/original"
    write(source + "/RESULT.json", {"status": "PASS"})
    write(source + "/GENERATION_REUSE.json", {"source_candidate": paid.replace("/", "\\")})
    result = write(paid + "/RESULT.json", {"status": "FAIL"})
    ledger = write("older/REQUEST_LEDGER.jsonl", {})
    catalog = write("older/MODEL_CATALOG.json", [{"id": "deepseek-flash"}])
    unrelated = write("unrelated/REQUEST_LEDGER.jsonl", {})
    write("artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z/HISTORY_INDEX_V3.json", {"source_sha256": {}})
    (tmp_path / "old/source_revisions/runtime-v0").mkdir(parents=True)
    out = tmp_path / "current"
    write("current/BASELINE_CENSUS.json", {"pairs": [{"id": "replayed", "source_directory": str(tmp_path / source),
        "source_runtime_sha256": "runtime-v0"}]})
    files, bindings = package.selection(out)
    assert {ledger, catalog, result} <= set(files) and unrelated not in files
    binding = bindings["generation_cost_and_reuse_bindings"][source]
    assert binding["chain_directories"] == [source, paid]
    assert binding["files"]["older/REQUEST_LEDGER.jsonl"] == package.pack.digest_file(ledger)
    assert binding["files"]["older/MODEL_CATALOG.json"] == package.pack.digest_file(catalog)
    assert paid in bindings["sealed_candidate_directories"]


def test_selection_preserves_ignored_egg_info_in_authoritative_runtime_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    tracked = tmp_path / "src/ioabench/module.py"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("value = 1\n", encoding="utf-8")
    metadata = set()
    for name in ("PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt", "requires.txt", "top_level.txt"):
        path = tmp_path / "src/ioa_bench.egg-info" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("retained local metadata: " + name + "\n", encoding="utf-8")
        metadata.add(path)
    (tmp_path / ".gitignore").write_text("*.egg-info/\n", encoding="utf-8")
    monkeypatch.setattr(package.subprocess, "check_output", lambda *args, **kwargs: b"src/ioabench/module.py\0")
    out = tmp_path / "current"
    out.mkdir()
    (out / "BASELINE_CENSUS.json").write_text('{"pairs": []}', encoding="utf-8")
    prior = tmp_path / "artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z/HISTORY_INDEX_V3.json"
    prior.parent.mkdir(parents=True)
    prior.write_text('{"source_sha256": {}}', encoding="utf-8")
    expected = package.source_tree_hash(tmp_path)
    files, bindings = package.selection(out)
    assert metadata <= set(files)
    archive = tmp_path / "runtime.zip"
    package.write_archive(archive, files, {}, {"runtime_sha256": expected, **bindings}, ())
    assert package.verify_archive(archive)["all_file_sha256_match"] is True
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(extracted)
    assert package.source_tree_hash(extracted / "ioa_codex_spec") == expected
    assert all(path.is_file() for path in metadata)


@pytest.mark.parametrize("name", ["config/local.key", "src/.env", "src/.pytest_cache/state.json", "src/loose.pyc", "src/runtime.lock"])
def test_excluded_authoritative_runtime_input_fails_closed(tmp_path, monkeypatch, name):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    monkeypatch.setattr(package.subprocess, "check_output", lambda *args, **kwargs: b"")
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_text("excluded fixture", encoding="utf-8")
    out = tmp_path / "current"
    out.mkdir()
    (out / "BASELINE_CENSUS.json").write_text('{"pairs": []}', encoding="utf-8")
    prior = tmp_path / "artifacts/v5/provider_benchmark/round02-resume-20261020T024920Z/HISTORY_INDEX_V3.json"
    prior.parent.mkdir(parents=True)
    prior.write_text('{"source_sha256": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="authoritative runtime contains excluded files"):
        package.selection(out)
    assert path.read_text(encoding="utf-8") == "excluded fixture"


@pytest.mark.parametrize("problem", ["cycle", "escape", "changed-source", "receipt-escape"])
def test_generation_reuse_and_accounting_fail_closed(tmp_path, problem):
    source, target = tmp_path / "run/candidates/reuse", tmp_path / "run/candidates/paid"
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    value = {"source_candidate": str(source if problem == "cycle" else tmp_path.parent / "outside" if problem == "escape" else target)}
    if problem == "changed-source":
        value["source_result_sha256"] = "wrong"
        (target / "RESULT.json").write_text("{}", encoding="utf-8")
    if problem == "receipt-escape":
        (tmp_path / "run/REQUEST_LEDGER.jsonl").write_text(json.dumps({"receipt_path": "../../outside.json"}) + "\n", encoding="utf-8")
    (source / "GENERATION_REUSE.json").write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="cycle|escapes|binding changed"):
        package.generation_evidence(source, tmp_path)


def test_generation_cost_archive_binding_rejects_missing_ledger_member(tmp_path, handoff):
    files, snapshot = handoff
    ledger = tmp_path / "prior/REQUEST_LEDGER.jsonl"
    ledger.parent.mkdir()
    ledger.write_text("{}\n", encoding="utf-8")
    snapshot["generation_cost_and_reuse_bindings"] = {"prior/candidates/original": {
        "files": {"prior/REQUEST_LEDGER.jsonl": package.pack.digest_file(ledger)}}}
    incomplete = tmp_path / "missing-paid-ledger.zip"
    package.write_archive(incomplete, files, {}, snapshot, ())
    with pytest.raises(ValueError, match="bound archive evidence"):
        package.verify_archive(incomplete)
    complete = tmp_path / "bound-paid-ledger.zip"
    package.write_archive(complete, files + [ledger], {}, snapshot, ())
    assert package.verify_archive(complete)["generation_cost_and_reuse_bindings"] == "PASS"


@pytest.mark.parametrize('failure', [None, 'resume', 'replay', 'provider'])
def test_extracted_verification_executes_cli_and_rejects_failed_or_paid_receipts(tmp_path, monkeypatch, failure):
    extracted = tmp_path / 'extracted'
    script = extracted / 'scripts/v5/verify_development_factory.py'
    script.parent.mkdir(parents=True)
    script.write_text('# fixture verifier', encoding='utf-8')
    receipt = tmp_path / 'EXTRACTED_VERIFICATION.json'
    result = {'status': 'PASS', 'provider_calls': 0, 'ledger_unchanged': True,
        'required_positive_replays': 'PASS', 'actual_cli_resume': {'status': 'PASS'}}
    if failure == 'resume':
        result['actual_cli_resume']['status'] = 'FAIL'
    elif failure == 'replay':
        result['required_positive_replays'] = 'FAIL'
    elif failure == 'provider':
        result['provider_calls'] = 1
    calls = []
    def execute(command, **options):
        calls.append((command, options))
        receipt.write_text(json.dumps(result), encoding='utf-8')
    monkeypatch.setattr(package.subprocess, 'run', execute)
    if failure:
        with pytest.raises(ValueError, match='did not pass'):
            package.verify_extracted(extracted, Path('artifacts/round'), receipt)
    else:
        assert package.verify_extracted(extracted, Path('artifacts/round'), receipt) == result
    command, options = calls[0]
    assert command[:3] == [sys.executable, '-B', str(script)]
    assert command[command.index('--protection-scope') + 1] == 'included'
    assert command[command.index('--root') + 1] == str(extracted)
    assert command[command.index('--out') + 1] == str(extracted / 'artifacts/round')
    assert options['check'] is True and options['cwd'] == extracted
