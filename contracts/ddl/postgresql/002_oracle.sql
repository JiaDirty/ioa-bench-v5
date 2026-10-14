-- IoA-Bench PostgreSQL Oracle DDL
-- Target database: ioabench_oracle
-- PostgreSQL >= 16
-- SECURITY BOUNDARY: this DB is ECP-only. No SUT principal may CONNECT.
-- Truth is append/version only. UPDATE/DELETE are prohibited by trigger for truth tables.

BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS oracle;
REVOKE ALL ON SCHEMA oracle FROM PUBLIC;

CREATE TABLE oracle.truth_sets (
    truth_set_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_key            text NOT NULL,
    version                 text NOT NULL,
    content_sha256          char(64) NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
    effective_policy        text NOT NULL CHECK (effective_policy IN ('static_for_run','versioned_timevarying')),
    metadata                jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scenario_key, version, content_sha256)
);

CREATE TABLE oracle.run_truth_bindings (
    run_id                  uuid PRIMARY KEY,
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    bound_at                timestamptz NOT NULL DEFAULT now(),
    binding_sha256          char(64) NOT NULL CHECK (binding_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE oracle.identity_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    agent_id                text NOT NULL,
    real_principal_id       text NOT NULL,
    organization_id         text NOT NULL,
    trust_domain_id         text NOT NULL,
    issuer                  text,
    credential_fingerprint  text,
    valid                   boolean NOT NULL DEFAULT true,
    valid_from              timestamptz,
    valid_until             timestamptz,
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (truth_set_id, agent_id, valid_from)
);
CREATE INDEX identity_truth_lookup_idx ON oracle.identity_truth (truth_set_id, agent_id, valid_from, valid_until);

CREATE TABLE oracle.capability_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    agent_id                text NOT NULL,
    capability              text NOT NULL,
    supported               boolean NOT NULL,
    competence_level        double precision CHECK (competence_level IS NULL OR competence_level BETWEEN 0 AND 1),
    evidence_ref            text,
    valid_from              timestamptz,
    valid_until             timestamptz,
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (truth_set_id, agent_id, capability, valid_from)
);
CREATE INDEX capability_truth_lookup_idx ON oracle.capability_truth (truth_set_id, agent_id, capability);

CREATE TABLE oracle.authorization_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    delegation_id           text,
    issuer_principal_id     text NOT NULL,
    subject_principal_id    text NOT NULL,
    action                  text NOT NULL,
    resource                text NOT NULL,
    scope                   text[] NOT NULL DEFAULT ARRAY[]::text[],
    audience                text[] NOT NULL DEFAULT ARRAY[]::text[],
    max_delegation_depth    integer CHECK (max_delegation_depth IS NULL OR max_delegation_depth >= 0),
    redelegation_allowed    boolean NOT NULL DEFAULT false,
    parent_delegation_id    text,
    valid_from              timestamptz,
    valid_until             timestamptz,
    constraints             jsonb NOT NULL DEFAULT '{}'::jsonb,
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX authorization_truth_subject_idx ON oracle.authorization_truth (truth_set_id, subject_principal_id, action, resource);
CREATE INDEX authorization_truth_delegation_idx ON oracle.authorization_truth (truth_set_id, delegation_id);

CREATE TABLE oracle.protocol_semantic_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    source_protocol         text NOT NULL,
    source_version          text NOT NULL,
    source_symbol           text NOT NULL,
    target_protocol         text NOT NULL,
    target_version          text NOT NULL,
    target_symbol           text NOT NULL,
    relation                text NOT NULL CHECK (relation IN ('equivalent','narrower','broader','incompatible','requires_context')),
    required_context        jsonb NOT NULL DEFAULT '{}'::jsonb,
    side_effect_semantics   jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (truth_set_id, source_protocol, source_version, source_symbol, target_protocol, target_version, target_symbol)
);

CREATE TABLE oracle.claim_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    proposition_id          text NOT NULL,
    truth_value             text NOT NULL CHECK (truth_value IN ('true','false','unknown')),
    valid_from              timestamptz,
    valid_until             timestamptz,
    evidence_refs           text[] NOT NULL DEFAULT ARRAY[]::text[],
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (truth_set_id, proposition_id, valid_from)
);
CREATE INDEX claim_truth_lookup_idx ON oracle.claim_truth (truth_set_id, proposition_id, valid_from, valid_until);

CREATE TABLE oracle.topology_node_truth (
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    node_id                 text NOT NULL,
    node_kind               text NOT NULL,
    organization_id         text,
    trust_domain_id         text,
    criticality             double precision NOT NULL DEFAULT 0 CHECK (criticality BETWEEN 0 AND 1),
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (truth_set_id, node_id)
);

CREATE TABLE oracle.topology_edge_truth (
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    source_node_id          text NOT NULL,
    target_node_id          text NOT NULL,
    edge_kind               text NOT NULL,
    directed                boolean NOT NULL DEFAULT true,
    attributes              jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (truth_set_id, source_node_id, target_node_id, edge_kind)
);

CREATE TABLE oracle.policy_norm_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    rule_id                 text NOT NULL,
    subject_selector        jsonb NOT NULL DEFAULT '{}'::jsonb,
    action                  text NOT NULL,
    resource_selector       jsonb NOT NULL DEFAULT '{}'::jsonb,
    normative_status        text NOT NULL CHECK (normative_status IN ('required','permitted','prohibited','unspecified')),
    valid_from              timestamptz,
    valid_until             timestamptz,
    rationale_ref           text,
    UNIQUE (truth_set_id, rule_id, valid_from)
);

CREATE TABLE oracle.utility_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    utility_function_id     text NOT NULL,
    version                 text NOT NULL,
    definition              jsonb NOT NULL,
    sha256                  char(64) NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (truth_set_id, utility_function_id, version)
);

CREATE TABLE oracle.human_task_truth (
    truth_id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_set_id            uuid NOT NULL REFERENCES oracle.truth_sets(truth_set_id) ON DELETE RESTRICT,
    task_ref                text NOT NULL,
    answer_key              jsonb NOT NULL,
    scoring_key             jsonb NOT NULL DEFAULT '{}'::jsonb,
    difficulty              double precision CHECK (difficulty IS NULL OR difficulty BETWEEN 0 AND 1),
    UNIQUE (truth_set_id, task_ref)
);

CREATE OR REPLACE FUNCTION oracle.reject_truth_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Oracle truth tables are append/version-only; UPDATE/DELETE prohibited on %', TG_TABLE_NAME;
END;
$$;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'truth_sets','run_truth_bindings','identity_truth','capability_truth','authorization_truth',
    'protocol_semantic_truth','claim_truth','topology_node_truth','topology_edge_truth',
    'policy_norm_truth','utility_truth','human_task_truth'
  ]
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS reject_truth_mutation ON oracle.%I', t);
    EXECUTE format('CREATE TRIGGER reject_truth_mutation BEFORE UPDATE OR DELETE ON oracle.%I FOR EACH ROW EXECUTE FUNCTION oracle.reject_truth_mutation()', t);
  END LOOP;
END $$;

COMMIT;
