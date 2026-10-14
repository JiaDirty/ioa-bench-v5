# SQLite local-v1 storage

Apply `001_control.sql` to `control.db`, `002_oracle.sql` to `oracle.db`, `003_sut.sql` to `sut.db`, and `004_telemetry.sql` to `telemetry.db`.

The files MUST remain separate. Tested-agent processes must never receive the Oracle database path/handle. These schemas are normative for local v1; PostgreSQL/ClickHouse files are optional scale-out references.
