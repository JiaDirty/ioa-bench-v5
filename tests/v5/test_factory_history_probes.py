import importlib.util
import gzip
import hashlib
import io
import json
from pathlib import Path
from dataclasses import replace
import zipfile

import pytest

from ioabench.v5.ai_generation.history import build_index
from ioabench.v5.dynamic import t331_slice


def script():
    path = Path(__file__).resolve().parents[2] / "scripts/v5/probe_factory_history.py"
    spec = importlib.util.spec_from_file_location("probe_factory_history", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def indexed_case(tmp_path, *, unsupported=False, suffix=".json"):
    case = t331_slice.generate(seed=31, families=1)[0][0]
    if unsupported:
        world = dict(case.world)
        world.pop("chain")
        case = replace(case, world=world)
    source = tmp_path / ("cases" + suffix)
    source.write_text(json.dumps(case.as_dict()) + "\n", encoding="utf-8")
    path = tmp_path / "INDEX.json"
    path.write_text(json.dumps(build_index(tmp_path, sources=[source])), encoding="utf-8")
    return source, path, tmp_path / "probes"


def saved_case(output):
    path = next((output / "cases").glob("*.gz"))
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return path, json.load(stream)


def write_saved(path, saved):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(saved, stream)
    path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest(), encoding="ascii")


def test_real_historical_probes_resume_without_execution_and_reject_tampering(tmp_path, monkeypatch):
    pair = next(iter(t331_slice.generate(seed=31, families=1)))
    source = tmp_path / "cases.jsonl"
    source.write_text(json.dumps(pair[0].as_dict()) + "\n\n" + json.dumps(pair[1].as_dict()) + "\n", encoding="utf-8")
    index = build_index(tmp_path, sources=[source])
    path = tmp_path / "INDEX.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    module = script()
    output = tmp_path / "probes"
    report = module.probe(tmp_path, path, output, ["T331"])
    assert report["selected_cases"] == 2
    assert report["by_suite"]["T331"] == {"PROBED": 2}
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("resume executed a policy again"))
    assert module.probe(tmp_path, path, output, ["T331"]) == report
    retained = next((output / "cases").glob("*.gz"))
    retained.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="evidence digest"):
        module.probe(tmp_path, path, output, ["T331"])


@pytest.mark.parametrize("field", ["POLICY_CONTRACT", "QUALITY_VERSION", "PROBE_VERSION", "source_tree_hash"])
def test_resume_rejects_runtime_quality_and_behavior_contract_conflicts(tmp_path, monkeypatch, field):
    _, index, output = indexed_case(tmp_path)
    module = script()
    module.probe(tmp_path, index, output, ["T331"])
    monkeypatch.setattr(module, field, (lambda root: "changed-runtime") if field == "source_tree_hash" else "changed-version")
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("contract conflict executed a policy"))
    with pytest.raises(ValueError, match="contract changed"):
        module.probe(tmp_path, index, output, ["T331"])


@pytest.mark.parametrize("field", ["case_sha256", "suite_id", "run_contract_sha256", "source_occurrence", "policy_execution", "probe_policy", "probe_evidence", "result_records"])
def test_resume_revalidates_case_source_policy_and_trace_even_when_file_digest_is_rebound(tmp_path, monkeypatch, field):
    _, index, output = indexed_case(tmp_path)
    module = script()
    module.probe(tmp_path, index, output, ["T331"])
    path, saved = saved_case(output)
    if field == "probe_policy":
        saved["probe"]["policy_contract"] = "another-policy"
    elif field == "probe_evidence":
        saved["probe"]["evidence_sha256"]["witness"] = "f" * 64
    elif field == "result_records":
        saved["results"]["witness"]["trace"]["records"] = []
    elif field == "source_occurrence":
        saved[field]["pointer"] = "/another-case"
    else:
        saved[field] = "changed"
    write_saved(path, saved)
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("evidence conflict executed a policy"))
    with pytest.raises(ValueError):
        module.probe(tmp_path, index, output, ["T331"])


def test_resume_rejects_changed_original_source_and_changed_index(tmp_path, monkeypatch):
    source, index, output = indexed_case(tmp_path)
    module = script()
    module.probe(tmp_path, index, output, ["T331"])
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("source conflict executed a policy"))
    original = source.read_bytes()
    source.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="source changed or missing"):
        module.probe(tmp_path, index, output, ["T331"])
    source.write_bytes(original)
    index.write_bytes(index.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="contract changed"):
        module.probe(tmp_path, index, output, ["T331"])


def test_unsupported_historical_runtime_is_explicit_and_resumes_without_rerun(tmp_path, monkeypatch):
    _, index, output = indexed_case(tmp_path, unsupported=True)
    module = script()
    report = module.probe(tmp_path, index, output, ["T331"])
    assert report["status"] == "COMPLETED_WITH_EXPLICIT_GAPS"
    assert report["by_suite"]["T331"] == {"INDETERMINATE": 1}
    _, saved = saved_case(output)
    assert saved["schema_version"] == module.EVIDENCE_VERSION
    assert saved["probe"] is None and saved["probe_status"] == "NOT_RUN"
    assert saved["policy_execution"] == {"witness": "FAILED", "naive": "NOT_RUN"}
    assert saved["error_type"] == "KeyError" and saved["results"] == {}
    enriched = json.loads((output / "INDEX_WITH_PROBES.json").read_text(encoding="utf-8"))
    assert enriched["records"][0]["behavioral_probe_signature"] is None
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("unsupported case was executed again"))
    assert module.probe(tmp_path, index, output, ["T331"]) == report


def test_unbound_occurrence_is_indeterminate_without_reading_an_external_case(tmp_path, monkeypatch):
    _, index, output = indexed_case(tmp_path)
    document = json.loads(index.read_text(encoding="utf-8"))
    document["records"][0]["occurrences"][0]["source"] = "unbound.json"
    index.write_text(json.dumps(document), encoding="utf-8")
    module = script()
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("unbound source executed a policy"))
    report = module.probe(tmp_path, index, output, ["T331"])
    assert report["by_suite"]["T331"] == {"INDETERMINATE": 1}
    _, saved = saved_case(output)
    assert saved["probe"] is None and saved["policy_execution"] == {"witness": "NOT_RUN", "naive": "NOT_RUN"}
    assert "unbound source" in saved["error"]


def test_retained_nested_archive_case_source_is_probed_and_original_archive_remains_bound(tmp_path, monkeypatch):
    case = t331_slice.generate(seed=31, families=1)[0][0]
    archive = tmp_path / "archive/retained.zip"
    archive.parent.mkdir()
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as stream:
        stream.writestr("pair.json", json.dumps(case.as_dict()))
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("nested.zip", nested.getvalue())
    helper_path = Path(__file__).resolve().parents[2] / "scripts/v5/build_history_index.py"
    spec = importlib.util.spec_from_file_location("history_archive_builder", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    source, inventory = helper.archive_cases(tmp_path, tmp_path / "retained-index")
    document = build_index(tmp_path, sources=[source])
    document["source_sha256"].update({name: row["sha256"] for name, row in inventory["archives"].items()})
    index = tmp_path / "INDEX.json"
    index.write_text(json.dumps(document), encoding="utf-8")
    module = script()
    output = tmp_path / "probes"
    report = module.probe(tmp_path, index, output, ["T331"])
    assert report["by_suite"]["T331"] == {"PROBED": 1}
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("archive resume executed a policy"))
    assert module.probe(tmp_path, index, output, ["T331"]) == report
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("pair.json", "[]")
    with pytest.raises(ValueError, match="source changed or missing"):
        module.probe(tmp_path, index, output, ["T331"])


def test_uppercase_jsonl_source_keeps_physical_blank_line_positions(tmp_path):
    source, index, output = indexed_case(tmp_path, suffix=".JSONL")
    source.write_text("\n" + source.read_text(encoding="utf-8"), encoding="utf-8")
    index.write_text(json.dumps(build_index(tmp_path, sources=[source])), encoding="utf-8")
    assert script().probe(tmp_path, index, output, ["T331"])["by_suite"]["T331"] == {"PROBED": 1}


def test_interrupted_probe_resumes_only_unfinished_cases(tmp_path, monkeypatch):
    pair = t331_slice.generate(seed=31, families=1)[0]
    source = tmp_path / "cases.json"
    source.write_text(json.dumps([case.as_dict() for case in pair]), encoding="utf-8")
    index = tmp_path / "INDEX.json"
    index.write_text(json.dumps(build_index(tmp_path, sources=[source])), encoding="utf-8")
    module = script()
    original = module.run_dynamic_case
    def interrupt_second(root, case, *args, **kwargs):
        if case.case_id == pair[1].case_id:
            raise KeyboardInterrupt("simulated process interruption")
        return original(root, case, *args, **kwargs)
    monkeypatch.setattr(module, "run_dynamic_case", interrupt_second)
    output = tmp_path / "probes"
    with pytest.raises(KeyboardInterrupt):
        module.probe(tmp_path, index, output, ["T331"])
    assert len(list((output / "cases").glob("*.gz"))) == 1
    rerun = []
    def remaining_only(root, case, *args, **kwargs):
        assert case.case_id == pair[1].case_id, "completed case was executed again"
        rerun.append(case.case_id)
        return original(root, case, *args, **kwargs)
    monkeypatch.setattr(module, "run_dynamic_case", remaining_only)
    assert module.probe(tmp_path, index, output, ["T331"])["by_suite"]["T331"] == {"PROBED": 2}
    assert rerun == [pair[1].case_id, pair[1].case_id]


def test_empty_selection_is_not_run(tmp_path, monkeypatch):
    _, index, output = indexed_case(tmp_path)
    module = script()
    monkeypatch.setattr(module, "run_dynamic_case", lambda *a, **k: pytest.fail("unselected suite was executed"))
    report = module.probe(tmp_path, index, output, ["T352"])
    assert report["status"] == "NOT_RUN" and report["selected_cases"] == 0


def test_classic_case_proof_is_recomputed_on_resume_with_ledger_evidence(tmp_path, monkeypatch):
    from ioabench.v5.suites import t331
    case = t331.generate(seed=31, families=1)[0][0]
    source = tmp_path / "case.json"
    source.write_text(json.dumps(case.as_dict()), encoding="utf-8")
    index = tmp_path / "INDEX.json"
    index.write_text(json.dumps(build_index(tmp_path, sources=[source])), encoding="utf-8-sig")
    module = script()
    output = tmp_path / "probes"
    report = module.probe(tmp_path, index, output, ["T331"])
    assert report["by_suite"]["T331"] == {"PROBED": 1}
    _, saved = saved_case(output)
    assert all(result["monitor_report"]["ledger_integrity"]["passed"] for result in saved["results"].values())
    monkeypatch.setattr(module, "run_case", lambda *a, **k: pytest.fail("classic resume executed a policy"))
    assert module.probe(tmp_path, index, output, ["T331"]) == report
