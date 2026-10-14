from ioabench.security import SecretRedactor


def test_redactor_covers_nested_telemetry_and_exception_paths() -> None:
    key = "secret-value-123"
    redactor = SecretRedactor.from_environment({"AIHUBMIX_API_KEY": key})

    payload = redactor.value({"message": f"failed: {key}", "nested": [key]})
    assert payload == {"message": "failed: [REDACTED_SECRET]", "nested": ["[REDACTED_SECRET]"]}
    assert redactor.exception(RuntimeError(f"provider response contained {key}")) == "provider response contained [REDACTED_SECRET]"
    assert key not in repr(redactor)
