from pathlib import Path

from ioabench.worlds import load_worlds


def test_six_worlds_are_schema_valid_and_cross_two_domains() -> None:
    worlds = load_worlds(Path(__file__).parents[2] / "worlds")

    assert len(worlds) == 6
    assert {world["world_id"] for world in worlds} == {
        "W01_ENTERPRISE_OPS", "W02_FINANCIAL_SERVICES", "W03_RESEARCH_LAB",
        "W04_LOGISTICS_SUPPLY", "W05_CLOUD_SOFTWARE", "W06_ADMIN_CASEWORK",
    }
    assert all(len(world["organizations"]) >= 2 for world in worlds)
    assert all(world["seed"] >= 100 for world in worlds)
