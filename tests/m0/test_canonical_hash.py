from ioabench.hashing import canonical_json_bytes, canonical_sha256


def test_canonical_hash_ignores_mapping_order_and_formatting() -> None:
    first = {"b": [1, 2], "a": {"y": True, "x": "值"}}
    second = {"a": {"x": "值", "y": True}, "b": [1, 2]}

    assert canonical_sha256(first) == canonical_sha256(second)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)

