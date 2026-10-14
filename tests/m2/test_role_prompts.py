from pathlib import Path

from ioabench.worlds import load_roles


def test_role_library_is_neutral_and_does_not_name_canonical_risks() -> None:
    roles = load_roles(Path(__file__).parents[2] / "roles" / "roles.yaml")
    forbidden = {"T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333", "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363"}

    assert {"coordinator", "analyst", "service_agent", "reviewer", "operator"} <= roles.keys()
    for role in roles.values():
        assert role["prompt"]
        assert not forbidden.intersection(role["prompt"].split())
