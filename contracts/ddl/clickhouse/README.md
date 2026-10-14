# ClickHouse optional scale-out telemetry profile

This is a future high-volume telemetry profile and **not a v1 dependency**. Local v1 uses `telemetry.db` via SQLite plus filesystem replay artifacts.

If enabled later, it must preserve the same normalized event semantics, model-call provenance, truth separation and replay requirements. Oracle truth must never be ingested into a tested-agent-visible telemetry path.
