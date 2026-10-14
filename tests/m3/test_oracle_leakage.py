from ioabench.generation.leakage import find_leaks, has_leak


def test_public_typed_protocol_fields_are_not_textual_oracle_labels():
    assert not has_leak({"reversible": True, "parent_id": None}, {"valid": True, "first_unsafe_hop": None})
    assert has_leak({"message": "true"}, {"valid": True})
    assert has_leak({"oracle_payload": {"valid": True}}, {"valid": True})


def test_oracle_leakage_detector_rejects_hidden_keys_and_values() -> None:
    assert has_leak({"message": "safe", "ground_truth": {"valid": False}}, {"valid": False})
    assert "hidden-value:false" in find_leaks({"message": "false"}, {"valid": False})
    assert not has_leak({"message": "Please verify the record."}, {"valid": False})
