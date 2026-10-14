# PostgreSQL optional scale-out profile

These migrations are retained for a future service-based deployment. They are **not required by local v1** and must not block the no-Docker reference benchmark.

The separation intent remains useful: control state, hidden Oracle truth and SUT-visible state live in distinct databases/credentials. If this profile is implemented, tested-agent runtimes must never receive Oracle credentials or network access.

Before using this profile, Codex must re-run migration smoke tests against the selected PostgreSQL version and reconcile schema differences with the normative local-v1 data model through an ADR/migration, not by silently changing benchmark semantics.
