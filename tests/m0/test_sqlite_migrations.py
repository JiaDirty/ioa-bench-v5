from pathlib import Path

from ioabench.storage.sqlite import LocalStores, StoreRole


ROOT = Path(__file__).parents[2]


def test_all_normative_sqlite_migrations_apply_to_clean_files(tmp_path: Path) -> None:
    stores = LocalStores.from_directory(tmp_path / "data", ROOT / "contracts" / "ddl" / "sqlite")
    stores.migrate()

    expected_tables = {
        StoreRole.CONTROL: {"experiments", "runs", "run_transitions", "scores", "artifacts", "generation_jobs"},
        StoreRole.ORACLE: {"truth_sets", "identity_truth", "capability_truth", "authorization_truth", "fact_truth", "protocol_truth", "topology_truth", "policy_truth", "task_truth"},
        StoreRole.SUT: {"organizations", "agents", "registry_records", "delegations", "tasks", "messages", "claims", "reputation", "sandbox_state"},
        StoreRole.TELEMETRY: {"events", "model_calls", "replay_index"},
    }
    for role, tables in expected_tables.items():
        with stores.connect(role) as connection:
            actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables <= actual
