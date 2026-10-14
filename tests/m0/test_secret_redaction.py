from ioabench.config import SecretStore


def test_api_key_is_environment_only_and_redacted() -> None:
    key = "test-secret-key"
    secrets = SecretStore.from_environment({"AIHUBMIX_API_KEY": key, "OTHER": "ignored"})

    assert secrets.get("AIHUBMIX_API_KEY") == key
    assert key not in repr(secrets)
    assert secrets.redact(f"provider failed with {key}") == "provider failed with [REDACTED_SECRET]"


def test_missing_api_key_is_allowed_for_offline_work() -> None:
    assert SecretStore.from_environment({}).get("AIHUBMIX_API_KEY") is None
