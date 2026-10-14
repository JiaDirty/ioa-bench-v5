-- IoA-Bench PostgreSQL SUT DDL
-- Target database: ioabench_sut
-- PostgreSQL >= 16
-- Normative: operational, fallible, attacker-influenced state visible to SUT services.
-- It MUST NOT contain hidden oracle labels.

BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS sut;
REVOKE ALL ON SCHEMA sut FROM PUBLIC;

CREATE TABLE sut.organizations (
    organization_id         text PRIMARY KEY,
    trust_domain_id         text NOT NULL,
    registry_namespace      text,
    identity_issuer         text,
    policy_domain           text,
    network_zone            text,
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    active                  boolean NOT NULL DEFAULT true
);
CREATE INDEX organizations_trust_domain_idx ON sut.organizations (trust_domain_id);

CREATE TABLE sut.agents (
    agent_id                text PRIMARY KEY,
    organization_id         text NOT NULL REFERENCES sut.organizations(organization_id) ON DELETE RESTRICT,
    runtime_instance_id     text NOT NULL,
    kind                    text NOT NULL CHECK (kind IN ('scripted','remote_a2a','llm','malicious','observer','mock_human')),
    claimed_public_identity text,
    verified_identity_ref   text,
    endpoint                text,
    status                  text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','revoked','offline')),
    runtime_config          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, runtime_instance_id)
);
CREATE INDEX agents_org_idx ON sut.agents (organization_id, status);

CREATE TABLE sut.agent_claims (
    claim_record_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                text NOT NULL REFERENCES sut.agents(agent_id) ON DELETE CASCADE,
    claim_type              text NOT NULL CHECK (claim_type IN ('identity','organization','capability','authority','security','endpoint','other')),
    claim_key               text NOT NULL,
    claim_value             jsonb NOT NULL,
    source                  text NOT NULL,
    signature_status        text CHECK (signature_status IS NULL OR signature_status IN ('valid','invalid','missing','unknown')),
    observed_at             timestamptz NOT NULL DEFAULT now(),
    revoked_at              timestamptz
);
CREATE INDEX agent_claims_lookup_idx ON sut.agent_claims (agent_id, claim_type, claim_key, observed_at DESC);

CREATE TABLE sut.agent_records (
    record_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    registry_namespace      text,
    record_format           text NOT NULL CHECK (record_format IN ('a2a_agent_card','oasf','custom')),
    record_version          text NOT NULL,
    raw_record              jsonb NOT NULL,
    payload_sha256          char(64) NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    signature_status        text CHECK (signature_status IS NULL OR signature_status IN ('valid','invalid','missing','unknown')),
    visible                 boolean NOT NULL DEFAULT true,
    published_at            timestamptz NOT NULL DEFAULT now(),
    expires_at              timestamptz,
    revoked_at              timestamptz
);
CREATE INDEX agent_records_discovery_idx ON sut.agent_records (registry_namespace, visible, published_at DESC);
CREATE INDEX agent_records_agent_idx ON sut.agent_records (agent_id, published_at DESC);

CREATE TABLE sut.registry_discovery_log (
    discovery_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid,
    querying_agent_id       text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    query                   jsonb NOT NULL,
    result_record_ids       uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
    scores                  jsonb NOT NULL DEFAULT '[]'::jsonb,
    selected_record_id      uuid REFERENCES sut.agent_records(record_id) ON DELETE SET NULL,
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sut.credentials (
    credential_id           text PRIMARY KEY,
    agent_id                text REFERENCES sut.agents(agent_id) ON DELETE CASCADE,
    issuer                  text NOT NULL,
    credential_type         text NOT NULL,
    public_fingerprint      text,
    claims                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    status                  text NOT NULL CHECK (status IN ('active','revoked','expired','invalid')),
    valid_from              timestamptz,
    valid_until             timestamptz,
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX credentials_agent_idx ON sut.credentials (agent_id, status);

CREATE TABLE sut.delegations (
    delegation_id           text PRIMARY KEY,
    run_id                  uuid,
    issuer_principal_id     text NOT NULL,
    subject_principal_id    text NOT NULL,
    parent_delegation_id    text REFERENCES sut.delegations(delegation_id) DEFERRABLE INITIALLY DEFERRED,
    scopes                  text[] NOT NULL DEFAULT ARRAY[]::text[],
    resources               text[] NOT NULL DEFAULT ARRAY[]::text[],
    audiences               text[] NOT NULL DEFAULT ARRAY[]::text[],
    valid_from              timestamptz,
    valid_until             timestamptz,
    max_delegation_depth    integer CHECK (max_delegation_depth IS NULL OR max_delegation_depth >= 0),
    redelegation_allowed    boolean NOT NULL DEFAULT false,
    depth                   integer NOT NULL DEFAULT 0 CHECK (depth >= 0),
    status                  text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked','expired','rejected')),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX delegations_subject_idx ON sut.delegations (subject_principal_id, status);
CREATE INDEX delegations_parent_idx ON sut.delegations (parent_delegation_id);

CREATE TABLE sut.authorization_decisions (
    decision_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid,
    subject_principal_id    text NOT NULL,
    action                  text NOT NULL,
    resource                text NOT NULL,
    delegation_id           text REFERENCES sut.delegations(delegation_id) ON DELETE SET NULL,
    context                 jsonb NOT NULL DEFAULT '{}'::jsonb,
    decision                text NOT NULL CHECK (decision IN ('allow','deny','indeterminate','error')),
    policy_ref              text,
    reason                  text,
    checked_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX authz_decisions_lookup_idx ON sut.authorization_decisions (run_id, subject_principal_id, action, resource, checked_at);

CREATE TABLE sut.tasks (
    task_id                 text PRIMARY KEY,
    run_id                  uuid,
    owner_agent_id          text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    state                   text NOT NULL,
    protocol                text,
    protocol_version        text,
    input_ref               text,
    output_ref              text,
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tasks_run_idx ON sut.tasks (run_id, state);

CREATE TABLE sut.messages (
    message_id              text PRIMARY KEY,
    run_id                  uuid,
    task_id                 text REFERENCES sut.tasks(task_id) ON DELETE SET NULL,
    source_agent_id         text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    target_agent_id         text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    protocol                text NOT NULL,
    protocol_version        text NOT NULL,
    content_ref             text,
    content_sha256          char(64) CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[a-f0-9]{64}$'),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    sent_at                 timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX messages_run_task_idx ON sut.messages (run_id, task_id, sent_at);

CREATE TABLE sut.actions (
    action_id               text PRIMARY KEY,
    run_id                  uuid,
    task_id                 text REFERENCES sut.tasks(task_id) ON DELETE SET NULL,
    actor_agent_id          text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    action_type             text NOT NULL,
    resource                text,
    delegation_id           text REFERENCES sut.delegations(delegation_id) ON DELETE SET NULL,
    requested_payload_ref   text,
    outcome                 text CHECK (outcome IS NULL OR outcome IN ('success','failure','denied','unknown')),
    side_effect_ref         text,
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz
);
CREATE INDEX actions_run_idx ON sut.actions (run_id, actor_agent_id, created_at);

CREATE TABLE sut.knowledge_claims (
    claim_id                text PRIMARY KEY,
    proposition_id          text,
    content_ref             text,
    content_sha256          char(64) CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[a-f0-9]{64}$'),
    source_agent_id         text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    source_type             text NOT NULL CHECK (source_type IN ('agent','tool','external','human','synthetic','unknown')),
    asserted_truth          text CHECK (asserted_truth IS NULL OR asserted_truth IN ('true','false','unknown')),
    confidence              double precision CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    evidence_refs           text[] NOT NULL DEFAULT ARRAY[]::text[],
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE sut.claim_edges (
    edge_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid,
    parent_claim_id         text REFERENCES sut.knowledge_claims(claim_id) ON DELETE CASCADE,
    child_claim_id          text NOT NULL REFERENCES sut.knowledge_claims(claim_id) ON DELETE CASCADE,
    relation                text NOT NULL CHECK (relation IN ('derived_from','forwarded_from','endorses','contradicts','corrects','cites','launders_source','other')),
    actor_agent_id          text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (parent_claim_id IS NULL OR parent_claim_id <> child_claim_id)
);
CREATE INDEX claim_edges_parent_idx ON sut.claim_edges (parent_claim_id, created_at);
CREATE INDEX claim_edges_child_idx ON sut.claim_edges (child_claim_id, created_at);

CREATE TABLE sut.reputation_events (
    reputation_event_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid,
    agent_id                text NOT NULL REFERENCES sut.agents(agent_id) ON DELETE CASCADE,
    source_agent_id         text REFERENCES sut.agents(agent_id) ON DELETE SET NULL,
    event_type              text NOT NULL,
    delta                   double precision NOT NULL,
    reason_ref              text,
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX reputation_events_agent_idx ON sut.reputation_events (agent_id, created_at);

CREATE TABLE sut.reputation_state (
    agent_id                text PRIMARY KEY REFERENCES sut.agents(agent_id) ON DELETE CASCADE,
    score                   double precision NOT NULL,
    version                 bigint NOT NULL DEFAULT 0 CHECK (version >= 0),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sut.incentive_events (
    incentive_event_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid,
    agent_id                text NOT NULL REFERENCES sut.agents(agent_id) ON DELETE CASCADE,
    reward_function_id      text NOT NULL,
    reward                  double precision NOT NULL,
    local_components        jsonb NOT NULL DEFAULT '{}'::jsonb,
    externalities           jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX incentive_events_run_idx ON sut.incentive_events (run_id, agent_id, created_at);

CREATE TABLE sut.router_decisions (
    router_decision_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid,
    router_id               text NOT NULL,
    task_ref                text NOT NULL,
    candidate_agent_ids     text[] NOT NULL,
    feature_snapshot        jsonb NOT NULL,
    score_snapshot          jsonb NOT NULL,
    selected_agent_id       text,
    policy_ref              text,
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX router_decisions_run_idx ON sut.router_decisions (run_id, router_id, created_at);

COMMIT;
