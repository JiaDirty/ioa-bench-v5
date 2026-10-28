import csv
import json
from types import SimpleNamespace

from scripts.v5 import tf_r3_finalize as final


def test_ab_keeps_repairs_out_of_first_opportunities_and_checks_frozen_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(final, "ROOT", tmp_path)
    monkeypatch.setattr(final, "RUN", tmp_path)
    monkeypatch.setattr(final, "OUT", tmp_path)
    tasks = [{"id": f"R3-{suite}-x{i}", "suite": suite, "seed": i}
             for suite in ("T321", "T331", "T362") for i in range(1, 7)]
    (tmp_path / "TASK_SET_FROZEN_R3.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    entries = []
    for candidate, seed, status in (("R3-T321-x1-C", 1, "REJECTED"),
                                    ("R3-T321-x1-C-new", 99, "PASS")):
        directory = tmp_path / candidate
        directory.mkdir()
        (directory / "MANIFEST.json").write_text(json.dumps({"task": {**tasks[0], "seed": seed},
            "source_sha256": "source", "version": "factory", "development_policy": {"base_url": "endpoint"}}), encoding="utf-8")
        entries.append({"candidate": candidate, "directory": directory,
                        "result": {"route": "compositional_r3", "status": status},
                        "admission": {"status": "DEV_ACCEPTED"} if status == "PASS" else {}})
    monkeypatch.setattr(final, "attempts", lambda: entries)
    summary = final.ab_results({"requests": []})
    assert summary["route_opportunities"] == 36
    assert summary["first_outcomes"] == {"REJECTED": 1, "NOT_RUN": 35}
    assert summary["repairs"] == 1
    assert summary["per_suite_route"]["T321/compositional_r3"]["dev_accepted"] == 0
    assert summary["contract_violations"] == [{"candidate": "R3-T321-x1-C-new", "field": "seed"}]
    assert not summary["coverage_complete"]
    with (tmp_path / "FAILURE_FUNNEL_ALL.csv").open(encoding="utf-8", newline="") as stream:
        assert sum(int(row["count"]) for row in csv.DictReader(stream)) == 37


def test_final_references_are_source_bound_and_report_actual_resume(tmp_path, monkeypatch):
    from ioabench.v5.ai_generation import direct_deepseek, pipeline
    from ioabench.v5.core import case
    import tf_r3_pool_index

    monkeypatch.setattr(final, "ROOT", tmp_path)
    monkeypatch.setattr(final, "RUN", tmp_path)
    monkeypatch.setattr(final, "OUT", tmp_path)
    binding = {"git_head": "final-head", "runtime_source_sha256": "final-source",
               "working_tree_diff_sha256": "preserved-overlay"}
    monkeypatch.setattr(final, "identity", lambda: binding)
    monkeypatch.setattr(final, "novelty_counterexamples", lambda: None)
    monkeypatch.setattr(tf_r3_pool_index, "main", lambda: None)
    (tmp_path / "WORKFLOW_NOVELTY_AUDIT.json").write_text('{"rows": []}', encoding="utf-8")
    source = tmp_path / "candidate"
    source.mkdir()
    result = {"status": "PASS", "task": {"suite": "T321", "seed": 7}}
    (source / "RESULT.json").write_text(json.dumps(result), encoding="utf-8")
    (source / "PAIR.json").write_text('[{"arm":"CONTROL"},{"arm":"RISK"}]', encoding="utf-8")
    monkeypatch.setattr(final, "attempts", lambda: [{"candidate": "R3-test", "directory": source, "result": result}])
    monkeypatch.setattr(case, "case_from_dict", lambda value, **kwargs: SimpleNamespace(**value))
    monkeypatch.setattr(pipeline, "suite_spec", lambda *args, **kwargs: SimpleNamespace(policies=("witness", "naive")))

    def strict(directory, spec, compiled):
        assert directory.parent.name == "final-head-" + final.canonical_sha256(binding)[:16]
        for policy in spec.policies:
            manifest = directory / "strict/artifacts/v5/evaluations" / f"strict-7-{policy}" / "manifest.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text('{}', encoding="utf-8")
        return 6

    monkeypatch.setattr(direct_deepseek, "strict_checks", strict)
    final.checks()
    first = final.read(tmp_path / "FINAL_STRICT_REPLAY.json")["records"][0]
    assert first["resumed_reference_policies"] == []
    assert first["fresh_reference_policies"] == ["witness", "naive"]
    final.checks()
    resumed = final.read(tmp_path / "FINAL_STRICT_REPLAY.json")["records"][0]
    assert resumed["resumed_reference_policies"] == ["witness", "naive"]
    assert resumed["fresh_reference_policies"] == []
    assert "RESUME" in resumed["mode"]
