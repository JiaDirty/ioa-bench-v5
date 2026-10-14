-- IoA-Bench PostgreSQL Control Plane DDL
-- Target database: ioabench_control
-- PostgreSQL >= 16
-- Normative: mutable orchestration state and final score metadata only.
-- Oracle truth MUST NOT be stored in this database.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS ecp;
REVOKE ALL ON SCHEMA ecp FROM PUBLIC;

CREATE TABLE ecp.scenarios (
    scenario_key            text PRIMARY KEY,
    test_id                 text NOT NULL CHECK (test_id ~ '^T(31[1-3]|32[1-3]|33[1-3]|34[1-3]|35[1-3]|36[1-3])$'),
    variant                 text NOT NULL CHECK (variant ~ '^[a-z0-9][a-z0-9._-]{1,127}$'),
    version                 text NOT NULL,
    risk                    text NOT NULL,
    mode                    text NOT NULL CHECK (mode IN ('automated','human_study','hybrid')),
    simulation_only         boolean NOT NULL,
    schema_version          text NOT NULL DEFAULT 'ioa.scenario.v1',
    source_uri              text,
    source_sha256           char(64) NOT NULL CHECK (source_sha256 ~ '^[a-f0-9]{64}$'),
    compiled_sha256         char(64) CHECK (compiled_sha256 IS NULL OR compiled_sha256 ~ '^[a-f0-9]{64}$'),
    scenario_document       jsonb NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    retired_at              timestamptz,
    UNIQUE (test_id, variant, version),
    CHECK (scenario_key = test_id || ':' || variant || '@' || version)
);

CREATE TABLE ecp.experiments (
    experiment_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    text NOT NULL,
    description             text,
    scenario_key            text NOT NULL REFERENCES ecp.scenarios(scenario_key) ON UPDATE RESTRICT ON DELETE RESTRICT,
    parameter_overrides     jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_conditions    text[] NOT NULL,
    requested_by            text,
    status                  text NOT NULL DEFAULT 'CREATED' CHECK (status IN (
                                'CREATED','QUEUED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED'
                            )),
    created_at              timestamptz NOT NULL DEFAULT now(),
    started_at              timestamptz,
    completed_at            timestamptz,
    CHECK (array_length(requested_conditions, 1) >= 1),
    CHECK (requested_conditions <@ ARRAY['C0_CONTROL','C1_BENIGN_FAILURE','C2_SINGLE_ADVERSARY','C3_COORDINATED_ADVERSARIES']::text[])
);

CREATE TABLE ecp.runs (
    run_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id           uuid NOT NULL REFERENCES ecp.experiments(experiment_id) ON DELETE RESTRICT,
    scenario_key            text NOT NULL REFERENCES ecp.scenarios(scenario_key) ON DELETE RESTRICT,
    condition               text NOT NULL CHECK (condition IN ('C0_CONTROL','C1_BENIGN_FAILURE','C2_SINGLE_ADVERSARY','C3_COORDINATED_ADVERSARIES')),
    repetition_index        integer NOT NULL CHECK (repetition_index >= 0),
    matrix_index            integer NOT NULL DEFAULT 0 CHECK (matrix_index >= 0),
    seed                    bigint NOT NULL CHECK (seed >= 0),
    lifecycle_state         text NOT NULL DEFAULT 'CREATED' CHECK (lifecycle_state IN (
                                'CREATED','PROVISIONING','BASELINE_READY','FAULT_ARMED','RUNNING','OBSERVING',
                                'SCORING','VALIDATING','COMPLETED','FAILED_SETUP','FAILED_EXECUTION',
                                'FAILED_SCORING','INVALID_RUN','CANCELLED'
                            )),
    invalid_reason          text,
    invalid_details         jsonb NOT NULL DEFAULT '{}'::jsonb,
    config_snapshot         jsonb NOT NULL,
    config_sha256           char(64) NOT NULL CHECK (config_sha256 ~ '^[a-f0-9]{64}$'),
    git_sha                 text NOT NULL,
    image_digests           jsonb NOT NULL DEFAULT '{}'::jsonb,
    protocol_versions       jsonb NOT NULL DEFAULT '{}'::jsonb,
    dependency_versions     jsonb NOT NULL DEFAULT '{}'::jsonb,
    model_manifest          jsonb NOT NULL DEFAULT '{}'::jsonb,
    injector_manifest       jsonb NOT NULL DEFAULT '{}'::jsonb,
    scorer_manifest         jsonb NOT NULL DEFAULT '{}'::jsonb,
    topology_snapshot       jsonb NOT NULL DEFAULT '{}'::jsonb,
    environment_fingerprint text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    started_at              timestamptz,
    ended_at                timestamptz,
    telemetry_flushed_at    timestamptz,
    cleanup_verified_at     timestamptz,
    UNIQUE (experiment_id, condition, repetition_index, matrix_index)
);

CREATE INDEX runs_experiment_idx ON ecp.runs (experiment_id, condition, repetition_index);
CREATE INDEX runs_state_idx ON ecp.runs (lifecycle_state, created_at);
CREATE INDEX runs_scenario_idx ON ecp.runs (scenario_key, condition);

CREATE TABLE ecp.run_state_transitions (
    transition_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    from_state              text,
    to_state                text NOT NULL,
    transition_key          text NOT NULL,
    request_id              text,
    details                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, transition_key)
);

CREATE INDEX run_transitions_run_idx ON ecp.run_state_transitions (run_id, occurred_at, transition_id);

CREATE TABLE ecp.run_components (
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    component_type          text NOT NULL CHECK (component_type IN (
                                'agent','organization','trust_domain','registry','identity','authz','gateway',
                                'tool','router','knowledge','reputation','incentive','observer','human_ui','other'
                            )),
    component_id            text NOT NULL,
    organization_id         text,
    trust_domain_id         text,
    implementation          text,
    endpoint_ref            text,
    config                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, component_type, component_id)
);

CREATE TABLE ecp.fault_instances (
    fault_instance_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    injector_id             text NOT NULL,
    injector_type           text NOT NULL,
    injector_version        text NOT NULL,
    config                  jsonb NOT NULL,
    config_sha256           char(64) NOT NULL CHECK (config_sha256 ~ '^[a-f0-9]{64}$'),
    status                  text NOT NULL DEFAULT 'DEFINED' CHECK (status IN ('DEFINED','ARMED','TRIGGERED','DISARMED','FAILED')),
    required_to_trigger     boolean NOT NULL DEFAULT true,
    trigger_count           integer NOT NULL DEFAULT 0 CHECK (trigger_count >= 0),
    armed_at                timestamptz,
    first_triggered_at      timestamptz,
    last_triggered_at       timestamptz,
    disarmed_at             timestamptz,
    UNIQUE (run_id, injector_id)
);

CREATE TABLE ecp.fault_triggers (
    trigger_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fault_instance_id       uuid NOT NULL REFERENCES ecp.fault_instances(fault_instance_id) ON DELETE CASCADE,
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    source_event_id         text,
    target_ref              jsonb NOT NULL DEFAULT '{}'::jsonb,
    mutation_before_hash    char(64),
    mutation_after_hash     char(64),
    trigger_metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    triggered_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX fault_triggers_run_idx ON ecp.fault_triggers (run_id, triggered_at);

CREATE TABLE ecp.run_artifacts (
    artifact_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    kind                    text NOT NULL CHECK (kind IN (
                                'scenario','compiled_plan','trace_export','causal_graph','propagation_graph',
                                'raw_payload','report_json','report_markdown','report_html','log_bundle',
                                'dataset_snapshot','other'
                            )),
    uri                     text NOT NULL,
    sha256                  char(64) NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes              bigint CHECK (size_bytes IS NULL OR size_bytes >= 0),
    media_type              text,
    privacy_class           text NOT NULL DEFAULT 'internal' CHECK (privacy_class IN ('public','internal','restricted','sensitive')),
    created_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, kind, sha256)
);

CREATE TABLE ecp.run_validations (
    validation_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    check_id                text NOT NULL,
    phase                   text NOT NULL CHECK (phase IN ('preflight','baseline','postrun','prescore','postscore','cleanup')),
    status                  text NOT NULL CHECK (status IN ('PASS','FAIL','WARN','SKIP')),
    severity                text NOT NULL CHECK (severity IN ('info','warning','error','fatal')),
    details                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    checked_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, check_id, phase)
);

CREATE TABLE ecp.metric_definitions (
    metric_name             text NOT NULL,
    metric_version          text NOT NULL,
    test_id                 text CHECK (test_id IS NULL OR test_id ~ '^T(31[1-3]|32[1-3]|33[1-3]|34[1-3]|35[1-3]|36[1-3])$'),
    direction               text NOT NULL CHECK (direction IN ('higher_is_worse','lower_is_worse','descriptive')),
    unit                    text,
    value_type              text NOT NULL CHECK (value_type IN ('float','integer','boolean','string','json')),
    description             text NOT NULL,
    PRIMARY KEY (metric_name, metric_version)
);

CREATE TABLE ecp.run_metrics (
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE CASCADE,
    metric_name             text NOT NULL,
    metric_version          text NOT NULL,
    scorer_version          text NOT NULL,
    value_float             double precision,
    value_integer           bigint,
    value_boolean           boolean,
    value_string            text,
    value_json              jsonb,
    numerator               double precision,
    denominator             double precision,
    sample_count            bigint CHECK (sample_count IS NULL OR sample_count >= 0),
    confidence              double precision CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    evidence_event_ids      text[] NOT NULL DEFAULT ARRAY[]::text[],
    details                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    computed_at             timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, metric_name, metric_version),
    FOREIGN KEY (metric_name, metric_version) REFERENCES ecp.metric_definitions(metric_name, metric_version),
    CHECK (num_nonnulls(value_float, value_integer, value_boolean, value_string, value_json) = 1)
);

CREATE INDEX run_metrics_name_idx ON ecp.run_metrics (metric_name, metric_version, computed_at);

CREATE TABLE ecp.experiment_metric_summaries (
    experiment_id           uuid NOT NULL REFERENCES ecp.experiments(experiment_id) ON DELETE CASCADE,
    condition               text NOT NULL,
    metric_name             text NOT NULL,
    metric_version          text NOT NULL,
    n_valid                 integer NOT NULL CHECK (n_valid >= 0),
    n_invalid               integer NOT NULL DEFAULT 0 CHECK (n_invalid >= 0),
    mean                    double precision,
    median                  double precision,
    stddev                  double precision,
    min_value               double precision,
    max_value               double precision,
    ci_low                  double precision,
    ci_high                 double precision,
    confidence_level        double precision CHECK (confidence_level IS NULL OR confidence_level > 0 AND confidence_level < 1),
    quantiles               jsonb NOT NULL DEFAULT '{}'::jsonb,
    details                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    computed_at             timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (experiment_id, condition, metric_name, metric_version)
);

CREATE TABLE ecp.human_sessions (
    human_session_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid NOT NULL REFERENCES ecp.runs(run_id) ON DELETE RESTRICT,
    participant_pseudonym   text NOT NULL,
    protocol_ref            text NOT NULL,
    consent_record_ref      text,
    phase                   text,
    session_metadata        jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at              timestamptz,
    ended_at                timestamptz,
    UNIQUE (run_id, participant_pseudonym, phase)
);

CREATE TABLE ecp.human_decisions (
    decision_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    human_session_id        uuid NOT NULL REFERENCES ecp.human_sessions(human_session_id) ON DELETE CASCADE,
    task_ref                text NOT NULL,
    recommendation_ref      text,
    choice                  jsonb NOT NULL,
    overridden              boolean,
    independently_verified  boolean,
    response_time_ms        integer CHECK (response_time_ms IS NULL OR response_time_ms >= 0),
    recorded_at             timestamptz NOT NULL DEFAULT now()
);

COMMIT;
