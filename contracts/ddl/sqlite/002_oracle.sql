PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS truth_sets(
 truth_set_id TEXT PRIMARY KEY, test_id TEXT NOT NULL, version TEXT NOT NULL,
 content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, immutable INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS identity_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), subject_id TEXT NOT NULL,
 real_org_id TEXT, qualified INTEGER NOT NULL, attributes_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(truth_set_id,subject_id)
);
CREATE TABLE IF NOT EXISTS capability_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), agent_id TEXT NOT NULL,
 capability TEXT NOT NULL, verified INTEGER NOT NULL, level_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(truth_set_id,agent_id,capability)
);
CREATE TABLE IF NOT EXISTS authorization_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), authorization_id TEXT NOT NULL,
 issuer TEXT NOT NULL, subject TEXT NOT NULL, resource TEXT NOT NULL, scope_json TEXT NOT NULL,
 audience_json TEXT NOT NULL DEFAULT '[]', valid_from TEXT, valid_until TEXT, max_depth INTEGER,
 PRIMARY KEY(truth_set_id,authorization_id)
);
CREATE TABLE IF NOT EXISTS fact_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), fact_id TEXT NOT NULL,
 proposition_json TEXT NOT NULL, truth_value TEXT NOT NULL, rationale_json TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(truth_set_id,fact_id)
);
CREATE TABLE IF NOT EXISTS protocol_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), semantic_id TEXT NOT NULL,
 source_json TEXT NOT NULL, target_json TEXT NOT NULL, correct_mapping_json TEXT NOT NULL,
 PRIMARY KEY(truth_set_id,semantic_id)
);
CREATE TABLE IF NOT EXISTS topology_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), item_id TEXT NOT NULL,
 kind TEXT NOT NULL, truth_json TEXT NOT NULL, PRIMARY KEY(truth_set_id,item_id)
);
CREATE TABLE IF NOT EXISTS policy_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), policy_id TEXT NOT NULL,
 normative_rule_json TEXT NOT NULL, PRIMARY KEY(truth_set_id,policy_id)
);
CREATE TABLE IF NOT EXISTS task_truth(
 truth_set_id TEXT NOT NULL REFERENCES truth_sets(truth_set_id), task_id TEXT NOT NULL,
 expected_utility_json TEXT NOT NULL, valid_outcomes_json TEXT NOT NULL,
 PRIMARY KEY(truth_set_id,task_id)
);
