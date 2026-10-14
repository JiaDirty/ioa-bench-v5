# Testing

Offline tests run without provider credentials:

```text
python -m pytest -m "not integration"
```

Provider or external-service checks use the `integration` marker and are opt-in.
Regression tests use the `test_regression_<bug>` naming convention and must be
added whenever a defect is fixed.
