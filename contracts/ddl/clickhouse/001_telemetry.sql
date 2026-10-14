-- IoA-Bench ClickHouse Telemetry DDL
-- Target database: ioabench_telemetry
-- ClickHouse >= 24.x recommended
-- Append-only observation plane. Ground truth MUST NOT be stored here.

CREATE DATABASE IF NOT EXISTS ioabench_telemetry;

CREATE TABLE IF NOT EXISTS ioabench_telemetry.events_v1
(
    schema_version          LowCardinality(String),
    event_id                String,
    run_id                  UUID,
    event_time              DateTime64(6, 'UTC'),
    observed_at             DateTime64(6, 'UTC'),

    trace_id                String,
    span_id                 String,
    parent_span_id          String,

    actor_agent_id          LowCardinality(String),
    actor_organization_id   LowCardinality(String),
    actor_trust_domain_id   LowCardinality(String),
    target_agent_id         LowCardinality(String),
    target_organization_id  LowCardinality(String),
    target_trust_domain_id  LowCardinality(String),

    event_type              LowCardinality(String),
    protocol_name           LowCardinality(String),
    protocol_version        LowCardinality(String),
    transport               LowCardinality(String),

    task_id                 String,
    message_id              String,
    delegation_id           String,
    claim_id                String,
    action_id               String,

    outcome_status          LowCardinality(String),
    error_class             LowCardinality(String),

    payload_sha256          FixedString(64),
    payload_size_bytes      UInt64,
    content_ref             String,

    attributes_json         String,
    ingest_source           LowCardinality(String),
    ingest_batch_id         String,
    ingest_time             DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (run_id, event_time, event_id)
SETTINGS index_granularity = 8192;

ALTER TABLE ioabench_telemetry.events_v1
    ADD INDEX IF NOT EXISTS idx_event_type event_type TYPE set(2048) GRANULARITY 4;
ALTER TABLE ioabench_telemetry.events_v1
    ADD INDEX IF NOT EXISTS idx_trace trace_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE ioabench_telemetry.events_v1
    ADD INDEX IF NOT EXISTS idx_task task_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE ioabench_telemetry.events_v1
    ADD INDEX IF NOT EXISTS idx_delegation delegation_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE ioabench_telemetry.events_v1
    ADD INDEX IF NOT EXISTS idx_claim claim_id TYPE bloom_filter(0.01) GRANULARITY 4;

CREATE TABLE IF NOT EXISTS ioabench_telemetry.network_flows_v1
(
    run_id                  UUID,
    flow_id                 String,
    event_time              DateTime64(6, 'UTC'),
    observed_at             DateTime64(6, 'UTC'),
    source_pseudonym        LowCardinality(String),
    destination_pseudonym   LowCardinality(String),
    source_org_id           LowCardinality(String),
    destination_org_id      LowCardinality(String),
    source_trust_domain_id  LowCardinality(String),
    destination_trust_domain_id LowCardinality(String),
    transport               LowCardinality(String),
    protocol_name           LowCardinality(String),
    direction               LowCardinality(String),
    packet_or_message_count UInt32,
    bytes                   UInt64,
    duration_ms             UInt64,
    metadata_json           String,
    ingest_time             DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (run_id, event_time, source_pseudonym, destination_pseudonym, flow_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS ioabench_telemetry.otel_spans_v1
(
    run_id                  UUID,
    trace_id                String,
    span_id                 String,
    parent_span_id          String,
    trace_state             String,
    span_name               String,
    span_kind               LowCardinality(String),
    service_name            LowCardinality(String),
    organization_id         LowCardinality(String),
    trust_domain_id         LowCardinality(String),
    agent_id                LowCardinality(String),
    start_time              DateTime64(9, 'UTC'),
    end_time                DateTime64(9, 'UTC'),
    duration_ns             UInt64,
    status_code             LowCardinality(String),
    status_message          String,
    attributes_json         String,
    resource_json           String,
    events_json             String,
    links_json              String,
    ingest_time             DateTime64(6, 'UTC') DEFAULT now64(6)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(start_time)
ORDER BY (run_id, trace_id, start_time, span_id)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS ioabench_telemetry.protocol_translations_v1
(
    run_id                  UUID,
    translation_id          String,
    event_time              DateTime64(6, 'UTC'),
    gateway_id              LowCardinality(String),
    source_protocol         LowCardinality(String),
    source_version          LowCardinality(String),
    target_protocol         LowCardinality(String),
    target_version          LowCardinality(String),
    source_state            LowCardinality(String),
    target_state            LowCardinality(String),
    source_payload_sha256   FixedString(64),
    target_payload_sha256   FixedString(64),
    context_preserved       UInt8,
    trace_context_preserved UInt8,
    authz_context_preserved UInt8,
    idempotency_preserved   UInt8,
    translation_status      LowCardinality(String),
    error_class             LowCardinality(String),
    attributes_json         String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (run_id, event_time, gateway_id, translation_id);

CREATE TABLE IF NOT EXISTS ioabench_telemetry.claim_state_events_v1
(
    run_id                  UUID,
    event_time              DateTime64(6, 'UTC'),
    agent_id                LowCardinality(String),
    organization_id         LowCardinality(String),
    trust_domain_id         LowCardinality(String),
    claim_id                String,
    proposition_id          String,
    state                   LowCardinality(String),
    confidence              Nullable(Float64),
    source_claim_id         String,
    source_agent_id         LowCardinality(String),
    verified                UInt8,
    forwarded               UInt8,
    endorsed                UInt8,
    corrected               UInt8,
    round                   UInt32,
    attributes_json         String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (run_id, proposition_id, round, agent_id, event_time);

CREATE TABLE IF NOT EXISTS ioabench_telemetry.reputation_snapshots_v1
(
    run_id                  UUID,
    round                   UInt32,
    event_time              DateTime64(6, 'UTC'),
    agent_id                LowCardinality(String),
    organization_id         LowCardinality(String),
    score                   Float64,
    selection_count         UInt64,
    success_count           UInt64,
    quality_estimate        Nullable(Float64),
    attributes_json         String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY (run_id, round, agent_id);

-- Duplicate detector. The ingestion service MUST still enforce event_id idempotency;
-- this view only surfaces evidence of duplicate insertion.
CREATE VIEW IF NOT EXISTS ioabench_telemetry.event_duplicates_v1 AS
SELECT run_id, event_id, count() AS copies
FROM ioabench_telemetry.events_v1
GROUP BY run_id, event_id
HAVING copies > 1;

-- Common run-level event completeness view.
CREATE VIEW IF NOT EXISTS ioabench_telemetry.run_event_counts_v1 AS
SELECT
    run_id,
    event_type,
    count() AS event_count,
    min(event_time) AS first_event_time,
    max(event_time) AS last_event_time
FROM ioabench_telemetry.events_v1
GROUP BY run_id, event_type;

-- Trace orphan diagnostic: parent_span_id present but parent not observed in normalized events.
CREATE VIEW IF NOT EXISTS ioabench_telemetry.orphan_spans_v1 AS
SELECT child.run_id, child.trace_id, child.span_id, child.parent_span_id, child.event_time
FROM ioabench_telemetry.events_v1 AS child
LEFT JOIN ioabench_telemetry.events_v1 AS parent
    ON child.run_id = parent.run_id
   AND child.trace_id = parent.trace_id
   AND child.parent_span_id = parent.span_id
WHERE child.parent_span_id != '' AND parent.span_id = '';
