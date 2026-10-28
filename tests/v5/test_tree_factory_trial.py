"""The next trial covers all pilot/industry groups without recycling old IDs."""
from pathlib import Path
import json
import runpy


def test_trial_fills_underrepresented_cells_reproducibly(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    pool = [json.loads(line) for line in trial["POOL"].read_text(encoding="utf-8").splitlines()]
    tasks = trial["plan_tasks"](pool, "quality-test")
    assert tasks == trial["plan_tasks"](pool, "quality-test")
    assert len(tasks) == len({(task["suite"], task["industry"]) for task in tasks}) == 23
    assert {task['suite'] for task in tasks} == {'T311', 'T312', 'T313', 'T321', 'T322', 'T323', 'T331', 'T343', 'T351', 'T352', 'T353', 'T362'}
    assert all(task['industry'] == 'industry.payment_clearing' for task in tasks if task['suite'] == 'T322')
    assert all(task['assertions'] == ['T312-A1', 'T312-A2'] for task in tasks if task['suite'] == 'T312')
    assert all(task['business_transaction'] and 'T323-A3' in task['assertions']
               for task in tasks if task['suite'] == 'T323')
    assert {task["plan_focus"] for task in tasks} == {"extended_chain", "fork_join", "conditional"}
    old_ids = {row["candidate"] for row in pool}
    assert all(task["id"] not in old_ids and task["seed"] > 1000 for task in tasks)
    assert all(task["covered_workflows"] for task in tasks if task["industry"] != "industry.logistics" and task["suite"] not in {"T311", "T312", "T313", "T322", "T323", "T343", "T351", "T352", "T353"} and (
               task["suite"] != "T331" or task["industry"] != "industry.payment_clearing"))


def test_new_trial_routes_compile_their_declared_payloads(monkeypatch):
    from ioabench.v5.ai_generation.pipeline import suite_spec
    from ioabench.v5.ai_generation.tree_factory import assemble_blueprint
    from ioabench.v5.ai_generation.compiler_capabilities import dry_run_cell

    scripts = Path(__file__).resolve().parents[2] / 'scripts/v5'
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / 'tree_factory_trial.py'))
    tasks = [task for task in trial['plan_tasks']([], 'new-routes')
             if task['suite'] in {'T311', 'T313', 'T322', 'T343', 'T351'} or task['industry'] == 'industry.logistics']
    assert len(tasks) == 9
    for task in tasks:
        assert dry_run_cell(task['suite'], task['target'], seed=task['seed'])['status'] == 'SUPPORTED'
        spec = suite_spec(task['suite'], typed=True)
        pair = spec.adapter.compile_pair(assemble_blueprint(spec, task['target'], task), seed=task['seed'])
        assert spec.adapter.verify_arm_delta(*pair) == []
        assert task['assertions']
        if task['industry'] == 'industry.logistics':
            assert all(case.world['field_name'] == 'dispatch_cartons' for case in pair)


def test_later_trial_includes_previous_trial_admissions_once(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    registry = tmp_path / "r3.jsonl"
    registry.write_text(json.dumps({"evidence": "old"}) + "\n", encoding="utf-8")
    published = tmp_path / "artifacts/v5/data_factory/main_quality_previous/online/DEV_POOL_INDEX.jsonl"
    published.parent.mkdir(parents=True)
    published.write_text("\n".join(json.dumps({"evidence": name}) for name in ["old", "new"]) + "\n",
                         encoding="utf-8")
    scope = trial["historical_pool"].__globals__
    monkeypatch.setitem(scope, "ROOT", tmp_path)
    monkeypatch.setitem(scope, "POOL", registry)
    assert {row["evidence"] for row in trial["historical_pool"]()} == {"old", "new"}


def test_new_cohort_changes_seed_without_losing_reproducibility(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    first = trial["plan_tasks"]([], "r2-online")
    second = trial["plan_tasks"]([], "r3-online")
    assert [task["target"] for task in first] == [task["target"] for task in second]
    assert all(a["seed"] != b["seed"] and a["id"] != b["id"] for a, b in zip(first, second))


def test_stopped_terminal_resume_preserves_admissions_and_denominator(tmp_path, monkeypatch):
    import asyncio
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    scope = trial["run"].__globals__
    monkeypatch.setitem(scope, "source_tree_hash", lambda root: "source")
    def must_not_run(pool):
        raise AssertionError("terminal resume must not rebuild or rewrite the trial")
    monkeypatch.setitem(scope, "history_index", must_not_run)
    values = {"TRIAL_PLAN.json": {"source_sha256": "source",
               "historical_pool_sha256": trial["canonical_sha256"]([])},
              "HISTORY_POOL.json": [], "STOP.json": {"category": "REQUEST_UNRESOLVED"},
              "TRIAL_SUMMARY.json": {"planned_candidates": 6, "dev_accepted": ["retained"],
                                    "stopped": True}}
    for name, value in values.items():
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    result = asyncio.run(trial["run"](tmp_path))
    assert result == values["TRIAL_SUMMARY.json"]
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir()}


def test_failed_cell_does_not_monopolize_future_batches(monkeypatch):
    from collections import Counter
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    first = trial["plan_tasks"]([], "fresh")[0]
    failed = Counter({(first["suite"], first["industry"], first["plan_focus"]): 3})
    tasks = trial["plan_tasks"]([], "fresh", failed)
    selected = next(task for task in tasks if (task["suite"], task["industry"]) == (first["suite"], first["industry"]))
    assert selected["plan_focus"] != first["plan_focus"]
    assert tasks == trial["plan_tasks"]([], "fresh", failed)


def test_failure_counts_exclude_unstarted_and_accepted_opportunities(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    directory = tmp_path / "artifacts/v5/data_factory/main_quality_fixture/online"
    directory.mkdir(parents=True)
    task = {"id": "t", "suite": "T321", "industry": "industry.payment_clearing", "plan_focus": "fork_join"}
    (directory / "TRIAL_PLAN.json").write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    (directory / "TRIAL_SUMMARY.json").write_text(json.dumps({"rows": [
        {"task": "t", "status": "REJECTED"}, {"task": "t", "status": "NOT_RUN_GLOBAL_STOP"},
        {"task": "t", "status": "PASS", "admission": "DEV_ACCEPTED"}]}), encoding="utf-8")
    monkeypatch.setitem(trial["historical_failure_counts"].__globals__, "ROOT", tmp_path)
    assert trial["historical_failure_counts"]() == {("T321", "industry.payment_clearing", "fork_join"): 1}


def test_history_batch_retains_duplicate_sources_and_does_not_mutate_prior_index(tmp_path, monkeypatch):
    from copy import deepcopy
    import ioabench.v5.ai_generation.history as history

    scripts = Path(__file__).resolve().parents[2] / "scripts/v5"
    monkeypatch.syspath_prepend(str(scripts))
    trial = runpy.run_path(str(scripts / "tree_factory_trial.py"))
    old = {"source": "old", "status": "QUARANTINED"}
    new = {"source": "new", "status": "REJECTED"}
    index = {"records": [{"case_sha256": "same", "occurrences": [old],
                          "behavioral_probe_signature": {"original": True}}],
             "source_sha256": {"old": "pinned"}}
    before = deepcopy(index)
    paths = []

    def build_index(root, *, sources):
        paths.append(sources)
        return {"records": [{"case_sha256": "same", "occurrences": [old, new]},
                            {"case_sha256": "fresh", "occurrences": [new]}]}

    monkeypatch.setattr(history, "build_index", build_index)
    monkeypatch.setattr(trial["pilot"], "load_index", lambda: index)
    monkeypatch.setitem(trial["history_index"].__globals__, "ROOT", tmp_path)
    result = trial["history_index"]([{"evidence": "a"}, {"evidence": "b"}])
    assert paths == [[tmp_path / "a/PAIR.json", tmp_path / "b/PAIR.json"]]
    assert index == before
    assert result["records"][0]["occurrences"] == [old, new]
    assert result["records"][0]["behavioral_probe_signature"] == {"original": True}
    assert result["records"][1] == {"case_sha256": "fresh", "occurrences": [new]}
    assert result["source_sha256"] == index["source_sha256"]
